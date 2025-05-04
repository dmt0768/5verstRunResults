from flask import Flask, request, jsonify
import telebot
import threading
import requests
import time
import os
from pathlib import Path
from ThisRunStat import *

app = Flask(__name__)

# Путь к файлу с токеном
TOKEN_FILE = '/etc/secrets/key'


def read_token():
    try:
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Файл с токеном не найден: {TOKEN_FILE}")
        return None


TOKEN = read_token()
if not TOKEN:
    raise ValueError("Не удалось загрузить токен бота")

bot = telebot.TeleBot(TOKEN)
RENDER_URL = os.getenv('RENDER_URL', 'https://fiveverstrunresults.onrender.com')


def ping():
    while True:
        try:
            requests.get(RENDER_URL)
            print("Ping выполнен успешно")
        except Exception as e:
            print(f"Ошибка ping: {e}")
        time.sleep(300)  # 5 минут


@bot.message_handler(func=lambda message: True)
def general_message_handler(message):
    print("In general_message_handler")
    try:
        bot.reply_to(message, 'Echo ' + message.text)
    except Exception as e:
        print(f"Critical error2: {str(e)}")
        return 'server error', 500

    DEBUG = True
    answer = str()

    if DEBUG:
        link = 'https://5verst.ru/parkpobedy/results/latest/'
        link_valid = is_valid_result_url(link)
    else:
        link = message.text
        link_valid = is_valid_result_url(link)

    if link_valid:
        try:
            PS = ProcessorOfStart(link)
        except PageNotFound:
            print('Страница не найдена. Перезапустите программу, проверьте ссылку и попробуйте ещё раз')
            raise PageNotFound

        start = PS.process_start()
        [round_runs, round_vols] = start.get_round_clubs_runs_and_vols()
        answer += 'Всего участников: ' + str(start.get_participants_number()) + '\n' + '\n'
        answer += 'Из них неизвестных -- ' + str(start.get_unknown_participants_number()) + '\n' + '\n'
        answer += start.get_team_text() + '\n' + '\n'
        answer += "Круглые волонтёрства: \n" + print_round_clubs(round_vols) + '\n' + '\n'
        answer += "Круглые финиши: \n" + print_round_clubs(round_runs) + '\n' + '\n'
        rewards = start.get_rewards()
        answer += "Награды: \n" + print_reward_to_names(rewards) + '\n' + '\n'
        print(answer)
    else:
        print('Неправильная ссылка! Перезапустите программу, проверьте ссылку и попробуйте ещё раз')
        input()

    bot.reply_to(message, answer)


@app.route('/' + TOKEN, methods=['POST'])
def get_message():
    if request.headers.get('content-type') != 'application/json':
        return 'invalid content', 400

    try:
        json_data = request.get_json()
        print(f"Raw JSON: {json_data}")

        update = telebot.types.Update.de_json(json_data)
        if not update or not hasattr(update, 'message'):
            print("Пустое сообщение")
            return 'ok', 200

        # Принудительный запуск обработчика
        general_message_handler(update.message)

        return 'ok', 200

    except Exception as e:
        print(f"Critical error1: {str(e)}")
        return 'server error', 200


@app.route('/setwebhook')
def set_webhook():
    url = f'{RENDER_URL}/{TOKEN}'
    bot.remove_webhook()
    bot.set_webhook(url=url)
    return f'Webhook установлен на {url}', 200


@app.route('/')
def health_check():
    return jsonify({
        'status': 'active',
        'token_loaded': bool(TOKEN),
        'server': 'Render'
    }), 200


if __name__ == '__main__':
    # Проверка наличия токена при запуске
    if not TOKEN:
        print("ОШИБКА: Токен бота не загружен")
        exit(1)

    threading.Thread(target=ping, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
