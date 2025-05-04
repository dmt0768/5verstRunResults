import json
import os
import time
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse


class PageNotFound(Exception):
    pass


class DictOfList(dict):
    def add(self, key, value):
        if key in self:
            self[key].append(value)
        else:
            self[key] = [value]


class Participant:
    def __init__(self, name, runs, vols, rewards: set, roles: list, runner=False):
        self.name = name
        self.runner = runner
        self.roles = roles
        self.runs = runs
        self.vols = vols
        self.rewards = rewards

    def __gt__(self, other):
        return self.name > other.name


class Start:
    participants_ = dict()
    users_404 = 0
    team = str()

    def add_participant(self, participant_id, participant: Participant):
        if participant_id not in self.participants_.keys():
            self.participants_[participant_id] = participant
        else:
            self.update_participant(participant_id, participant)

    def update_participant(self, participant_id, participant: Participant):
        if participant_id not in self.participants_.keys():
            raise AttributeError("Участник с таким id ещё не создан")

        if (self.participants_[participant_id].name != participant.name or
                self.participants_[participant_id].runs != participant.runs or
                self.participants_[participant_id].vols != participant.vols):
            raise AttributeError("Произошло нечто ужасное. Похоже, что программа всё напутала...")

        if participant.roles is not None:
            self.participants_[participant_id].roles.append(participant.roles[0])

        if participant.runner:
            self.participants_[participant_id].runner = participant.runner

        self.participants_[participant_id].rewards.update(participant.rewards)


    def get_round_clubs_runs_and_vols(self):
        round_and_club_run_dict = DictOfList()
        round_and_club_vol_dict = DictOfList()
        for participant in self.participants_.values():
            if participant.runner and \
                    (participant.runs % 5 == 0 or
                     participant.runs % 10 == 0 or
                     participant.runs % 25 == 0) and \
                    (participant.runs != 0) and participant.runner:
                round_and_club_run_dict.add(participant.runs, participant)
            elif (participant.roles is not None) and \
                    (participant.vols % 5 == 0 or
                     participant.vols % 10 == 0 or
                     participant.vols % 25 == 0) and \
                    (participant.vols != 0) and \
                    len(participant.roles):
                round_and_club_vol_dict.add(participant.vols, participant)

        return round_and_club_run_dict, round_and_club_vol_dict

    def get_rewards(self):
        rewards_dict = dict()
        participant: Participant
        rewards: set
        for participant in self.participants_:
            rewards = self.participants_[participant].rewards
            if len(rewards):
                rewards_dict[self.participants_[participant].name] = self.participants_[participant].rewards
        return rewards_dict

    def get_participants_number(self):
        return len(self.participants_) + self.get_unknown_participants_number()

    def get_unknown_participants_number(self):
        return self.users_404

    def get_team_text(self):
        return self.team


class ProcessorOfStart:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.36 "
    }
    start = Start()

    def __init__(self, url):
        self.url = url
        self.response = self.__get_url_response(url)

    def process_start(self):
        soup = BeautifulSoup(self.response.text, 'html.parser')
        runners_table, volunteer_table = self.__get_tables(soup)
        self.__process_runnres_table(runners_table)
        self.__process_volunteer_table(volunteer_table)
        self.__get_vol_team_text(soup)
        return self.start

    def __get_url_response(self, url):
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response
        else:
            raise PageNotFound("URL недоступен")

    def __process_runnres_table(self, runners_table):
        for row in runners_table.find_all("tr"):
            try:
                user_id = self.__userlink_to_userid(row.find("a")['href'])
                name = row.find("a").string
                runs, vols = self.__parese_userstat(row.find('div', 'user-stat').findAll('span'))
                rewards = self.__parse_rewards(row.find('div', {'class': 'table-achievments'}))
                runner = True
                self.start.add_participant(user_id, Participant(name=name,
                                                                runs=runs,
                                                                vols=vols,
                                                                rewards=rewards,
                                                                roles=[],
                                                                runner=runner))
            except (AttributeError, TypeError):
                self.start.users_404 += 1

    def __process_volunteer_table(self, volunteer_table):
        for row in volunteer_table.find_all("tr"):
            user_id = self.__userlink_to_userid(row.find("a")['href'])
            name = row.find("a").string
            runs, vols = self.__parese_userstat(row.find('div', 'user-stat').findAll('span'))
            rewards = self.__parse_rewards(row.find('div', {'class': 'volunteer__role'}))
            role = [row.find('div', {'class': 'volunteer__role'}).find('span', title=None).text]
            self.start.add_participant(user_id, Participant(name=name,
                                                            runs=runs,
                                                            vols=vols,
                                                            rewards=rewards,
                                                            roles=role))
        return

    def __get_vol_team_text(self, soup):
        ans = soup.find('div', {'class': 'volunteer-list'}).text.strip().replace('\n', ' ')
        self.start.team = re.sub(' +', ' ', ans)

    @staticmethod
    def __get_tables(soup):
        runners_table = soup.find("table", {'id': 'results-table_runner'}).tbody
        volunteer_table = soup.find('th', string="Волонтёр").parent.parent.parent.tbody
        return runners_table, volunteer_table

    @staticmethod
    def __userlink_to_userid(link: str):
        user_id = link.split('/')[-1]
        try:
            int(user_id)
        except ValueError:
            raise AttributeError
        return user_id

    @staticmethod
    def __parese_userstat(userstat):
        run_stat = 0
        vol_stat = 0

        for stat in userstat:
            if 'финиш' in stat.string:
                run_stat = int(stat.string.split()[0])
            elif 'волонт' in stat.string:
                vol_stat = int(stat.string.split()[0])
            else:
                raise ValueError("Ошибка в парсинге статистики пользователя: неожиданный символ")
        return run_stat, vol_stat

    @staticmethod
    def __parse_rewards(rewards_html):
        rewards = set()
        for span in rewards_html.find_all('span', title=True):
            rewards.add(span.attrs['title'])

        return rewards


def is_valid_result_url(url):
    try:
        urlparse(url)
        if ('https://5verst.ru' == url[:17]) and ('results' in url):
            return True
        else:
            return False
    except ValueError:
        return False


def print_round_clubs(round_clubs):
    for round_number in sorted(round_clubs.keys()):
        participant: Participant
        for participant in sorted(round_clubs[round_number]):
            print(str(round_number) + ': ', end='')
            print(participant.name)


def print_name_to_rewards(rewards: dict):
    ans = str()
    for name in rewards:
        ans += name + ':\n'
        for reward in sorted(rewards[name]):
            ans += reward + '\n'
        print(ans)

        ans = str()


def print_reward_to_names(name_to_rewards: dict):
    all_rewards = set()
    reward_to_names = dict()
    for rewards_set in name_to_rewards.values():
        all_rewards.update(rewards_set)
    for reward in all_rewards:
        reward_to_names[reward] = set()
        for name in name_to_rewards:
            if reward in name_to_rewards[name]:
                reward_to_names[reward].add(name)

    for reward in reward_to_names:
        print(reward, ': ', sep='')
        for name in sorted(reward_to_names[reward]):
            print(name)
        print()


if __name__ == '__main__':
    DEBUG = True

    if DEBUG:
        link = 'https://5verst.ru/parkpobedy/results/latest/'
        link_valid = is_valid_result_url(link)
    else:
        link = input('Скопируйте ссылку: \n')
        link_valid = is_valid_result_url(link)

    if link_valid:
        try:
            PS = ProcessorOfStart(link)
        except PageNotFound:
            print('Страница не найдена. Перезапустите программу, проверьте ссылку и попробуйте ещё раз')
            input()
            raise PageNotFound

        start = PS.process_start()
        [round_runs, round_vols] = start.get_round_clubs_runs_and_vols()
        print()
        print('Всего участников:', start.get_participants_number())
        print('Из них неизвестных --', start.get_unknown_participants_number())
        print()
        print(start.get_team_text())
        print()
        print("Круглые волонтёрства:")
        print_round_clubs(round_vols)
        print()
        print("Круглые финиши:")
        print_round_clubs(round_runs)
        print()
        print('Награды')
        print()
        rewards = start.get_rewards()
        #print_name_to_rewards(rewards)
        print_reward_to_names(rewards)
        print()
        input()
    else:
        print('Неправильная ссылка! Перезапустите программу, проверьте ссылку и попробуйте ещё раз')
        input()
