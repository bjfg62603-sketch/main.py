import requests
import sqlite3
import random
import string
import time
import json
import os
from datetime import datetime

# ===== КОНФИГ =====
BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")  # ТОКЕН ОТ @BOTFATHER
ADMIN_IDS = [8428048355, 8164031956]
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ===== БАЗА ДАННЫХ =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        stars_spent INTEGER DEFAULT 0,
        reg_date TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER DEFAULT NULL,
        created_at TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tariff TEXT,
        stars_paid INTEGER,
        promo_code TEXT,
        date TEXT
    )
    """)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM promo_codes")
    if cursor.fetchone()[0] == 0:
        for _ in range(25):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            cursor.execute("INSERT INTO promo_codes (code, created_at) VALUES (?, ?)",
                           (code, datetime.now().isoformat()))
        conn.commit()
        print("✅ Добавлено 25 тестовых промо-кодов")

init_db()
print("✅ База данных инициализирована")

# ===== ФУНКЦИИ БД =====
def get_free_promo():
    cursor.execute("SELECT code FROM promo_codes WHERE is_used=0 LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None

def use_promo(code, user_id):
    cursor.execute("UPDATE promo_codes SET is_used=1, used_by=? WHERE code=?", (user_id, code))
    conn.commit()
    return cursor.rowcount > 0

def add_promo_codes(codes_list):
    added = 0
    for code in codes_list:
        try:
            cursor.execute("INSERT INTO promo_codes (code, created_at) VALUES (?, ?)",
                           (code, datetime.now().isoformat()))
            added += 1
        except:
            pass
    conn.commit()
    return added

def delete_promo(code):
    cursor.execute("DELETE FROM promo_codes WHERE code=?", (code,))
    conn.commit()
    return cursor.rowcount > 0

def get_all_promos(limit=50):
    cursor.execute("SELECT code, is_used, used_by FROM promo_codes LIMIT ?", (limit,))
    return cursor.fetchall()

def add_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (id, username, reg_date) VALUES (?, ?, ?)",
                   (user_id, username, datetime.now().isoformat()))
    conn.commit()

def add_purchase(user_id, tariff, stars, promo):
    cursor.execute("INSERT INTO purchases (user_id, tariff, stars_paid, promo_code, date) VALUES (?, ?, ?, ?, ?)",
                   (user_id, tariff, stars, promo, datetime.now().isoformat()))
    conn.commit()

def get_user_purchases(user_id):
    cursor.execute("SELECT tariff, promo_code, date FROM purchases WHERE user_id=? ORDER BY date DESC LIMIT 5", (user_id,))
    return cursor.fetchall()

def get_stats():
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_purchases = cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    total_stars = cursor.execute("SELECT SUM(stars_paid) FROM purchases").fetchone()[0] or 0
    free_promos = cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_used=0").fetchone()[0]
    return total_users, total_purchases, total_stars, free_promos

def get_all_users(limit=20):
    cursor.execute("SELECT id, username, stars_spent, reg_date FROM users ORDER BY reg_date DESC LIMIT ?", (limit,))
    return cursor.fetchall()

# ===== TELEGRAM API =====
def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
    url = f"{BASE_URL}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def answer_callback(callback_id, text="", show_alert=False):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id, "text": text, "show_alert": show_alert}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def send_invoice(chat_id, tariff_name, price, promo_code):
    url = f"{BASE_URL}/sendInvoice"
    payload = {
        "chat_id": chat_id,
        "title": f"Подписка {tariff_name}",
        "description": f"Доступ к PlutoniumDLL на {tariff_name}\nПромо-код: {promo_code}",
        "payload": f"{tariff_name}|{promo_code}",
        "provider_token": PAYMENT_PROVIDER_TOKEN,
        "currency": "XTR",
        "prices": [{"label": "Подписка", "amount": price}],
        "start_parameter": "plutonium_pay",
        "photo_url": "https://img.icons8.com/color/48/000000/security-checked--v1.png"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except:
        return {"ok": False}

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    payload = {"timeout": 30, "allowed_updates": ["message", "callback_query", "pre_checkout_query"]}
    if offset:
        payload["offset"] = offset
    try:
        resp = requests.post(url, json=payload, timeout=35)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except:
        pass
    return []

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "💎 Купить подписку", "callback_data": "buy"}],
            [{"text": "📋 Мои подписки", "callback_data": "my_subs"}],
            [{"text": "🆘 Поддержка", "callback_data": "support"}],
            [{"text": "📊 Статистика", "callback_data": "stats"}],
            [{"text": "⚙️ Админ-панель", "callback_data": "admin"}]
        ]
    }

def tariffs_menu():
    return {
        "inline_keyboard": [
            [{"text": "⭐ 7 дней — 50 ★", "callback_data": "tariff_7"}],
            [{"text": "⭐ 30 дней — 250 ★", "callback_data": "tariff_30"}],
            [{"text": "⭐ 90 дней — 500 ★", "callback_data": "tariff_90"}],
            [{"text": "👑 Навсегда — 600 ★", "callback_data": "tariff_forever"}],
            [{"text": "🔙 Назад", "callback_data": "back"}]
        ]
    }

def admin_menu():
    return {
        "inline_keyboard": [
            [{"text": "➕ Добавить промо-коды", "callback_data": "add_promo"}],
            [{"text": "➖ Удалить промо-код", "callback_data": "del_promo"}],
            [{"text": "📦 Список промо-кодов", "callback_data": "list_promo"}],
            [{"text": "👥 Список пользователей", "callback_data": "list_users"}],
            [{"text": "📈 Общая статистика", "callback_data": "admin_stats"}],
            [{"text": "🔙 Назад", "callback_data": "back"}]
        ]
    }

def back_button():
    return {"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back"}]]}

def support_menu():
    return {
        "inline_keyboard": [
            [{"text": "👤 @oryke — Техподдержка", "url": "https://t.me/oryke"}],
            [{"text": "👤 @shezik — Оплата", "url": "https://t.me/shezik"}],
            [{"text": "🔙 Назад", "callback_data": "back"}]
        ]
    }

# ===== ОБРАБОТЧИКИ =====
def handle_start(chat_id, username):
    add_user(chat_id, username)
    send_message(
        chat_id,
        "🔥 **PlutoniumDLL** — лучший софт для Standoff 2!\n\n"
        "💎 Премиум функции:\n"
        "• Aimbot\n"
        "• ESP (Wallhack)\n"
        "• Бесшумный режим\n"
        "• Анти-бан\n\n"
        "⬇️ Выберите действие:",
        main_menu()
    )

def handle_callback(callback):
    data = callback["data"]
    chat_id = callback["from"]["id"]
    msg_id = callback["message"]["message_id"]

    if data == "back":
        edit_message(chat_id, msg_id, "🔥 **Главное меню:**\nВыберите действие:", main_menu())
        answer_callback(callback["id"])
        return

    if data == "buy":
        edit_message(
            chat_id,
            msg_id,
            "💎 **Выберите тариф:**\n\n"
            "┌─────────────────────┐\n"
            "│ 7 дней — 50 ★      │\n"
            "│ 30 дней — 250 ★    │\n"
            "│ 90 дней — 500 ★    │\n"
            "│ Навсегда — 600 ★   │\n"
            "└─────────────────────┘",
            tariffs_menu()
        )
        answer_callback(callback["id"])
        return

    if data.startswith("tariff_"):
        tariff_map = {
            "tariff_7": ("7 дней", 50),
            "tariff_30": ("30 дней", 250),
            "tariff_90": ("90 дней", 500),
            "tariff_forever": ("Навсегда", 600)
        }
        tariff_name, price = tariff_map[data]
        promo = get_free_promo()
        if not promo:
            edit_message(
                chat_id,
                msg_id,
                "❌ **Промо-коды закончились!**\n\nОбратитесь в поддержку:",
                {"inline_keyboard": [[{"text": "🆘 Поддержка", "callback_data": "support"}]]}
            )
            answer_callback(callback["id"])
            return
        
        # Отправляем инвойс с кнопкой "Подтвердить и заплатить"
        result = send_invoice(chat_id, tariff_name, price, promo)
        if result.get("ok"):
            answer_callback(callback["id"], "💳 Счёт отправлен!")
        else:
            edit_message(
                chat_id,
                msg_id,
                f"❌ **Ошибка:** {result.get('description', 'Неизвестная ошибка')}\n\n"
                f"ℹ️ Убедитесь, что:\n"
                f"• У вас есть звёзды на балансе\n"
                f"• PAYMENT_PROVIDER_TOKEN настроен правильно",
                back_button()
            )
            answer_callback(callback["id"])
        return

    if data == "my_subs":
        purchases = get_user_purchases(chat_id)
        if not purchases:
            text = "❌ **У вас нет активных подписок.**"
            kb = {"inline_keyboard": [[{"text": "💎 Купить", "callback_data": "buy"}], [{"text": "🔙 Назад", "callback_data": "back"}]]}
        else:
            text = "📋 **Ваши подписки:**\n\n"
            for tariff, promo, date in purchases:
                text += f"▫️ **{tariff}** — `{promo}`\n"
            kb = back_button()
        edit_message(chat_id, msg_id, text, kb)
        answer_callback(callback["id"])
        return

    if data == "support":
        edit_message(
            chat_id,
            msg_id,
            "🆘 **Поддержка PlutoniumDLL**\n\n"
            "Если у вас возникли проблемы:\n"
            "• С оплатой\n"
            "• С активацией\n"
            "• С использованием софта\n\n"
            "Свяжитесь с нами:",
            support_menu()
        )
        answer_callback(callback["id"])
        return

    if data == "stats":
        total_users, total_purchases, total_stars, free_promos = get_stats()
        text = (
            "📊 **Общая статистика:**\n\n"
            f"👥 Пользователей: **{total_users}**\n"
            f"💳 Продаж: **{total_purchases}**\n"
            f"⭐ Звёзд заработано: **{total_stars}**\n"
            f"🎫 Свободных промо: **{free_promos}**"
        )
        edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

    if data == "admin":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Доступ запрещён!", True)
            return
        edit_message(chat_id, msg_id, "⚙️ **Админ-панель**\n\nВыберите действие:", admin_menu())
        answer_callback(callback["id"])
        return

    if data in ["add_promo", "del_promo", "list_promo", "list_users", "admin_stats"]:
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Доступ запрещён!", True)
            return

        if data == "add_promo":
            edit_message(chat_id, msg_id, "➕ **Добавление промо-кодов**\n\nИспользуйте команду:\n`/addpromo КОЛИЧЕСТВО`\nили\n`/addpromo КОД1,КОД2`", back_button())
        elif data == "del_promo":
            edit_message(chat_id, msg_id, "➖ **Удаление промо-кода**\n\nИспользуйте команду:\n`/delpromo КОД`", back_button())
        elif data == "list_promo":
            promos = get_all_promos()
            if not promos:
                text = "📭 **Нет промо-кодов.**"
            else:
                text = "📦 **Список промо-кодов:**\n\n"
                for code, used, used_by in promos:
                    status = "❌ Использован" if used else "✅ Свободен"
                    text += f"▫️ `{code}` — {status}" + (f" (user: {used_by})" if used_by else "") + "\n"
            edit_message(chat_id, msg_id, text, back_button())
        elif data == "list_users":
            users = get_all_users()
            if not users:
                text = "👥 **Нет пользователей.**"
            else:
                text = "👥 **Последние пользователи:**\n\n"
                for uid, uname, spent, reg in users:
                    text += f"▫️ {uname} (ID: `{uid}`) — потрачено: {spent}★, рег: {reg[:10]}\n"
            edit_message(chat_id, msg_id, text, back_button())
        elif data == "admin_stats":
            total_users, total_purchases, total_stars, free_promos = get_stats()
            text = (
                "📈 **Полная статистика:**\n\n"
                f"👥 Пользователей: **{total_users}**\n"
                f"💳 Продаж: **{total_purchases}**\n"
                f"⭐ Звёзд заработано: **{total_stars}**\n"
                f"🎫 Свободных промо: **{free_promos}**"
            )
            edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

def handle_pre_checkout(pre_checkout):
    """Обязательный обработчик для платежей"""
    url = f"{BASE_URL}/answerPreCheckoutQuery"
    payload = {
        "pre_checkout_query_id": pre_checkout["id"],
        "ok": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def handle_successful_payment(chat_id, payload, total_amount):
    try:
        tariff_name, promo_code = payload.split("|")
    except:
        tariff_name, promo_code = "Неизвестно", "Ошибка"
    
    if use_promo(promo_code, chat_id):
        add_purchase(chat_id, tariff_name, total_amount, promo_code)
        send_message(
            chat_id,
            f"✅ **Оплата подтверждена!**\n\n"
            f"📦 **Тариф:** {tariff_name}\n"
            f"💰 **Списано:** {total_amount} ★\n"
            f"🎫 **Ваш промо-код:**\n`{promo_code}`\n\n"
            f"🔗 **Активация:** https://plut.cc\n"
            f"📧 **Вопросы:** @oryke",
            back_button()
        )
        for admin in ADMIN_IDS:
            send_message(
                admin,
                f"💰 **Новая покупка!**\n\n"
                f"👤 Пользователь: `{chat_id}`\n"
                f"📦 Тариф: {tariff_name}\n"
                f"💰 Сумма: {total_amount} ★\n"
                f"🎫 Промо: `{promo_code}`"
            )
        print(f"💰 Покупка: {chat_id} -> {tariff_name} ({promo_code})")
    else:
        send_message(
            chat_id,
            "❌ **Ошибка активации промо-кода.**\nНапишите @oryke",
            back_button()
        )

def handle_message(chat_id, text, username):
    add_user(chat_id, username)

    if text.startswith("/addpromo"):
        if chat_id not in ADMIN_IDS:
            send_message(chat_id, "⛔ **Нет прав!**")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "❌ **Пример:**\n`/addpromo 5`\nили\n`/addpromo CODE1,CODE2`")
            return
        arg = parts[1].strip()
        if arg.isdigit():
            count = int(arg)
            codes = [''.join(random.choices(string.ascii_uppercase + string.digits, k=12)) for _ in range(count)]
            added = add_promo_codes(codes)
            send_message(chat_id, f"✅ **Добавлено {added} промо-кодов.**")
        else:
            codes = [c.strip() for c in arg.split(",") if c.strip()]
            added = add_promo_codes(codes)
            send_message(chat_id, f"✅ **Добавлено {added} промо-кодов.**")
        return

    if text.startswith("/delpromo"):
        if chat_id not in ADMIN_IDS:
            send_message(chat_id, "⛔ **Нет прав!**")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "❌ **Пример:**\n`/delpromo ABC123`")
            return
        code = parts[1].strip()
        if delete_promo(code):
            send_message(chat_id, f"✅ **Код `{code}` удалён.**")
        else:
            send_message(chat_id, f"❌ **Код `{code}` не найден.**")
        return

    if text.startswith("/crack"):
        purchases = get_user_purchases(chat_id)
        if not purchases:
            send_message(
                chat_id,
                "❌ **Доступ закрыт!**\n\nУ вас нет активной подписки.\nКупите доступ: /pay",
                {"inline_keyboard": [[{"text": "💎 Купить", "callback_data": "buy"}]]}
            )
            return
        last_promo = purchases[0][1]
        send_message(
            chat_id,
            f"✅ **Доступ открыт!**\n\n"
            f"🎫 **Ваш промо-код:**\n`{last_promo}`\n\n"
            f"🔗 **Активация:** https://plut.cc\n"
            f"📧 **Вопросы:** @oryke",
            back_button()
        )
        return

    if text == "/pay":
        send_message(chat_id, "💎 **Выберите тариф:**", tariffs_menu())
        return

    if text == "/price":
        send_message(
            chat_id,
            "📋 **Прайс-лист:**\n\n"
            "┌─────────────────────┐\n"
            "│ 7 дней — 50 ★      │\n"
            "│ 30 дней — 250 ★    │\n"
            "│ 90 дней — 500 ★    │\n"
            "│ Навсегда — 600 ★   │\n"
            "└─────────────────────┘\n\n"
            "Для покупки: /pay",
            back_button()
        )
        return

    if text == "/functions":
        send_message(
            chat_id,
            "📌 **Список команд:**\n\n"
            "🔹 **Основные:**\n"
            "`/start` — Главное меню\n"
            "`/pay` — Купить подписку\n"
            "`/price` — Прайс-лист\n"
            "`/crack` — Получить промо-код\n"
            "`/functions` — Список команд\n\n"
            "🔹 **Админ-команды:**\n"
            "`/addpromo N` — Добавить N промо\n"
            "`/addpromo CODE1,CODE2` — Добавить коды\n"
            "`/delpromo CODE` — Удалить промо",
            back_button()
        )
        return

    send_message(chat_id, "🔍 Используйте кнопки или /start", main_menu())

# ===== ОСНОВНОЙ ЦИКЛ =====
def main():
    print("🚀 Бот запущен на длинном поллинге с платежами!")
    last_update_id = 0

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            
            for update in updates:
                last_update_id = update["update_id"]

                # ===== PRE_CHECKOUT =====
                if "pre_checkout_query" in update:
                    handle_pre_checkout(update["pre_checkout_query"])
                    continue

                # ===== SUCCESSFUL PAYMENT =====
                if "message" in update:
                    msg = update["message"]
                    if "successful_payment" in msg:
                        chat_id = msg["from"]["id"]
                        payload = msg["successful_payment"]["invoice_payload"]
                        amount = msg["successful_payment"]["total_amount"]
                        handle_successful_payment(chat_id, payload, amount)
                        continue

                # ===== CALLBACK =====
                if "callback_query" in update:
                    handle_callback(update["callback_query"])
                    continue

                # ===== TEXT MESSAGE =====
                if "message" in update:
                    msg = update["message"]
                    if "text" in msg:
                        chat_id = msg["from"]["id"]
                        username = msg["from"].get("username", "NoName")
                        text = msg["text"]
                        
                        if text == "/start":
                            handle_start(chat_id, username)
                        else:
                            handle_message(chat_id, text, username)

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)

        time.sleep(0.5)

if __name__ == "__main__":
    main()
