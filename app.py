import requests
import sqlite3
import random
import string
import time
import json
from datetime import datetime

BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_IDS = [8428048355, 8164031956]
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, reg_date TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS promo_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, is_used INTEGER DEFAULT 0, used_by INTEGER DEFAULT NULL, created_at TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tariff TEXT, promo_code TEXT, date TEXT)")
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM promo_codes")
    if cursor.fetchone()[0] == 0:
        for _ in range(25):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            cursor.execute("INSERT INTO promo_codes (code, created_at) VALUES (?, ?)", (code, datetime.now().isoformat()))
        conn.commit()

init_db()

def get_free_promo():
    cursor.execute("SELECT code FROM promo_codes WHERE is_used=0 LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None

def use_promo(code, user_id):
    cursor.execute("UPDATE promo_codes SET is_used=1, used_by=? WHERE code=?", (user_id, code))
    conn.commit()
    return cursor.rowcount > 0

def add_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (id, username, reg_date) VALUES (?, ?, ?)", (user_id, username, datetime.now().isoformat()))
    conn.commit()

def add_purchase(user_id, tariff, promo):
    cursor.execute("INSERT INTO purchases (user_id, tariff, promo_code, date) VALUES (?, ?, ?, ?)", (user_id, tariff, promo, datetime.now().isoformat()))
    conn.commit()

def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

def edit_message(chat_id, message_id, text, reply_markup=None):
    url = f"{BASE_URL}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

def answer_callback(callback_id, text=""):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id, "text": text}
    requests.post(url, json=payload)

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    payload = {"timeout": 30}
    if offset:
        payload["offset"] = offset
    resp = requests.post(url, json=payload, timeout=35)
    if resp.status_code == 200:
        return resp.json().get("result", [])
    return []

def main_menu():
    return {"inline_keyboard": [
        [{"text": "💎 Купить подписку", "callback_data": "buy"}],
        [{"text": "📋 Мои подписки", "callback_data": "my_subs"}],
        [{"text": "🆘 Поддержка", "callback_data": "support"}],
        [{"text": "📊 Статистика", "callback_data": "stats"}],
        [{"text": "⚙️ Админ-панель", "callback_data": "admin"}]
    ]}

def tariffs_menu():
    return {"inline_keyboard": [
        [{"text": "⭐ 7 дней — 50 ★", "callback_data": "tariff_7"}],
        [{"text": "⭐ 30 дней — 250 ★", "callback_data": "tariff_30"}],
        [{"text": "⭐ 90 дней — 500 ★", "callback_data": "tariff_90"}],
        [{"text": "👑 Навсегда — 600 ★", "callback_data": "tariff_forever"}],
        [{"text": "🔙 Назад", "callback_data": "back"}]
    ]}

def admin_menu():
    return {"inline_keyboard": [
        [{"text": "➕ Добавить промо", "callback_data": "add_promo"}],
        [{"text": "📦 Список промо", "callback_data": "list_promo"}],
        [{"text": "👥 Список пользователей", "callback_data": "list_users"}],
        [{"text": "📈 Статистика", "callback_data": "admin_stats"}],
        [{"text": "🔙 Назад", "callback_data": "back"}]
    ]}

def back_button():
    return {"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back"}]]}

def handle_start(chat_id, username):
    add_user(chat_id, username)
    send_message(chat_id, "🔥 PlutoniumDLL — лучший софт для Standoff 2!\nВыберите действие:", main_menu())

def handle_callback(callback):
    data = callback["data"]
    chat_id = callback["from"]["id"]
    msg_id = callback["message"]["message_id"]

    if data == "back":
        edit_message(chat_id, msg_id, "🔥 Главное меню:", main_menu())
        answer_callback(callback["id"])
        return

    if data == "buy":
        edit_message(chat_id, msg_id, "💎 Выберите тариф:", tariffs_menu())
        answer_callback(callback["id"])
        return

    if data.startswith("tariff_"):
        tariff_map = {"tariff_7": "7 дней", "tariff_30": "30 дней", "tariff_90": "90 дней", "tariff_forever": "Навсегда"}
        tariff_name = tariff_map[data]
        promo = get_free_promo()
        if not promo:
            edit_message(chat_id, msg_id, "❌ Промо-коды кончились. Напишите @oryke")
            answer_callback(callback["id"])
            return
        add_purchase(chat_id, tariff_name, promo)
        use_promo(promo, chat_id)
        edit_message(chat_id, msg_id, f"✅ Подписка {tariff_name} активирована!\n\nВаш промо-код: `{promo}`\nАктивация: https://plut.cc", back_button())
        answer_callback(callback["id"])
        return

    if data == "my_subs":
        cursor.execute("SELECT tariff, promo_code, date FROM purchases WHERE user_id=? ORDER BY date DESC LIMIT 5", (chat_id,))
        rows = cursor.fetchall()
        if not rows:
            text = "❌ Нет активных подписок."
        else:
            text = "📋 Ваши подписки:\n\n"
            for tariff, promo, date in rows:
                text += f"▫️ {tariff} — `{promo}`\n"
        edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

    if data == "support":
        edit_message(chat_id, msg_id, "🆘 Поддержка:\n@oryke — техподдержка\n@shezik — оплата", back_button())
        answer_callback(callback["id"])
        return

    if data == "stats":
        total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_purchases = cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        edit_message(chat_id, msg_id, f"📊 Статистика:\n👥 Пользователей: {total_users}\n💳 Продаж: {total_purchases}", back_button())
        answer_callback(callback["id"])
        return

    if data == "admin":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа")
            return
        edit_message(chat_id, msg_id, "⚙️ Админ-панель:", admin_menu())
        answer_callback(callback["id"])
        return

    if data in ["add_promo", "list_promo", "list_users", "admin_stats"]:
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа")
            return
        if data == "add_promo":
            edit_message(chat_id, msg_id, "Используйте /addpromo КОЛИЧЕСТВО", back_button())
        elif data == "list_promo":
            cursor.execute("SELECT code, is_used FROM promo_codes LIMIT 20")
            rows = cursor.fetchall()
            text = "📦 Промо-коды:\n"
            for code, used in rows:
                text += f"{'❌' if used else '✅'} `{code}`\n"
            edit_message(chat_id, msg_id, text, back_button())
        elif data == "list_users":
            cursor.execute("SELECT id, username, reg_date FROM users ORDER BY reg_date DESC LIMIT 20")
            rows = cursor.fetchall()
            text = "👥 Пользователи:\n"
            for uid, uname, reg in rows:
                text += f"▫️ {uname} (ID: {uid})\n"
            edit_message(chat_id, msg_id, text, back_button())
        elif data == "admin_stats":
            total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_purchases = cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
            free_promos = cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_used=0").fetchone()[0]
            edit_message(chat_id, msg_id, f"📈 Статистика:\n👥 {total_users}\n💳 {total_purchases}\n🎫 Свободных промо: {free_promos}", back_button())
        answer_callback(callback["id"])
        return

def handle_message(chat_id, text, username):
    add_user(chat_id, username)

    if text.startswith("/addpromo"):
        if chat_id not in ADMIN_IDS:
            send_message(chat_id, "⛔ Нет прав")
            return
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "❌ Пример: /addpromo 5")
            return
        count = int(parts[1])
        codes = [''.join(random.choices(string.ascii_uppercase + string.digits, k=12)) for _ in range(count)]
        added = 0
        for code in codes:
            try:
                cursor.execute("INSERT INTO promo_codes (code, created_at) VALUES (?, ?)", (code, datetime.now().isoformat()))
                added += 1
            except:
                pass
        conn.commit()
        send_message(chat_id, f"✅ Добавлено {added} промо-кодов.")
        return

    if text == "/start":
        handle_start(chat_id, username)
        return

    send_message(chat_id, "Используйте кнопки", main_menu())

def main():
    print("🚀 Бот запущен!")
    last_update_id = 0
    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                if "callback_query" in update:
                    handle_callback(update["callback_query"])
                elif "message" in update:
                    msg = update["message"]
                    if "text" in msg:
                        chat_id = msg["from"]["id"]
                        username = msg["from"].get("username", "NoName")
                        text = msg["text"]
                        handle_message(chat_id, text, username)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
