from flask import Flask, request, jsonify
import telebot
import threading
import requests
import time
import os
from pathlib import Path

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




@bot.message_handler(commands=['start'])
def send_welcome(message):
    print("Обрабатываю start")
    bot.reply_to(message, "start")


@bot.message_handler(commands=['status'])
def status(message):
    print("Обрабатываю status")
    bot.reply_to(message, "Статус: активен\nТокен загружен из защищённого хранилища")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    print("Обрабатываю message: True")
    bot.reply_to(message, 'Получено сообщение: ' + message.text)


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

        # Принудительный тест обработчика
        print("-- Тест обработчика --")
        handle_message(update.message)  # <-- Важно!

        # Стандартная обработка
        bot.process_new_updates([update])
        return 'ok', 200

    except Exception as e:
        print(f"Critical error: {str(e)}")
        return 'server error', 500


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
