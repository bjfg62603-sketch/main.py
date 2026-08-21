from flask import Flask, request, jsonify
import json
from config import BOT_TOKEN, WEBHOOK_PATH, BASE_URL
from handlers import handle_start, handle_callback, handle_message, handle_successful_payment
from database import init_db
import requests

app = Flask(__name__)
init_db()

# Установка вебхука при старте
@app.before_request
def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    webhook_url = BASE_URL + WEBHOOK_PATH
    resp = requests.post(url, json={"url": webhook_url})
    print("Webhook set:", resp.json())

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "OK", 200

    # Обработка сообщений
    if "message" in data:
        msg = data["message"]
        chat_id = msg["from"]["id"]
        username = msg["from"].get("username", "NoName")

        # Проверка на успешный платёж
        if "successful_payment" in msg:
            payload = msg["successful_payment"]["invoice_payload"]
            amount = msg["successful_payment"]["total_amount"]
            handle_successful_payment(chat_id, payload, amount)
        elif "text" in msg:
            text = msg["text"]
            if text == "/start":
                handle_start(chat_id, username)
            else:
                handle_message(chat_id, text, username)
        else:
            handle_start(chat_id, username)  # если пришло что-то другое

    # Обработка callback-запросов (кнопки)
    elif "callback_query" in data:
        callback = data["callback_query"]
        handle_callback(callback)

    return "OK", 200

@app.route("/")
def index():
    return "PlutoniumDLL Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
