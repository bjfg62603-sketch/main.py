import asyncio
from flask import Flask, request
from telethon import TelegramClient, functions, types
import requests

API_ID = 27532296
API_HASH = "a3b6a763d078496cc4986d4fe4de1195"
PHONE = "+77718798289"
BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_ID = 8428048355

app = Flask(__name__)
client = None
loop = asyncio.new_event_loop()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop)

async def start_client():
    global client
    client = TelegramClient("session", API_ID, API_HASH)
    await client.start(phone=PHONE)
    print("✅ Telethon клиент запущен")

async def freeze_task(target, count, chat_id):
    try:
        entity = await client.get_entity(f"@{target}")
    except:
        send_message(chat_id, f"❌ Пользователь @{target} не найден")
        return
    
    send_message(chat_id, f"🔨 Начинаю фриз @{target} ({count} жалоб)")
    success = 0
    
    for i in range(count):
        try:
            await client(functions.messages.ReportRequest(
                peer=entity,
                id=[],
                reason=types.InputReportReasonSpam(),
                message="Spam and scam"
            ))
            success += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            send_message(chat_id, f"❌ Ошибка: {str(e)[:50]}")
            break
    
    send_message(chat_id, f"✅ Готово! {success}/{count} репортов на @{target}")

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Bot is running", 200
    
    data = request.get_json()
    if not data or "message" not in data:
        return "ok", 200
    
    msg = data["message"]
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "")
    
    if user_id != ADMIN_ID:
        send_message(chat_id, "⛔ Доступ только админу")
        return "ok", 200
    
    if text.startswith("/freeze"):
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "Формат: /freeze @username [кол-во]")
            return "ok", 200
        
        target = parts[1].replace("@", "")
        count = int(parts[2]) if len(parts) > 2 else 100
        
        run_async(freeze_task(target, count, chat_id))
        send_message(chat_id, f"🚀 Запущен фриз @{target}")
    
    elif text.startswith("/start"):
        send_message(chat_id, "🤖 Бот активен. Используй /freeze @username 100")
    
    elif text.startswith("/status"):
        send_message(chat_id, "✅ Бот работает")
    
    return "ok", 200

if __name__ == "__main__":
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_client())
    app.run(host="0.0.0.0", port=10000)
