import json
import requests
import random
import string
from config import BOT_TOKEN, ADMIN_IDS, BASE_URL
from database import *

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

def answer_callback(callback_id, text="", show_alert=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id, "text": text, "show_alert": show_alert}
    requests.post(url, json=payload)

def send_invoice(chat_id, tariff_name, price, promo_code):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
    payload = {
        "chat_id": chat_id,
        "title": f"Подписка {tariff_name}",
        "description": f"Доступ к PlutoniumDLL на {tariff_name}",
        "payload": f"{tariff_name}|{promo_code}",
        "provider_token": PAYMENT_PROVIDER_TOKEN,
        "currency": "XTR",
        "prices": [{"label": "Подписка", "amount": price}],
        "start_parameter": "plutonium_pay"
    }
    return requests.post(url, json=payload).json()

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "💰 Купить подписку", "callback_data": "buy"}],
            [{"text": "📋 Мои подписки", "callback_data": "my_subs"}],
            [{"text": "🆘 Поддержка", "callback_data": "support"}],
            [{"text": "📊 Статистика", "callback_data": "stats"}],
            [{"text": "⚙️ Админ-панель", "callback_data": "admin"}]
        ]
    }

def tariffs_menu():
    return {
        "inline_keyboard": [
            [{"text": "7 дней — 50 ⭐", "callback_data": "tariff_7"}],
            [{"text": "30 дней — 250 ⭐", "callback_data": "tariff_30"}],
            [{"text": "90 дней — 500 ⭐", "callback_data": "tariff_90"}],
            [{"text": "Навсегда — 600 ⭐", "callback_data": "tariff_forever"}],
            [{"text": "🔙 Назад", "callback_data": "back"}]
        ]
    }

def admin_menu():
    return {
        "inline_keyboard": [
            [{"text": "➕ Добавить промо", "callback_data": "add_promo"}],
            [{"text": "➖ Удалить промо", "callback_data": "del_promo"}],
            [{"text": "📦 Список промо", "callback_data": "list_promo"}],
            [{"text": "👥 Список пользователей", "callback_data": "list_users"}],
            [{"text": "📈 Общая статистика", "callback_data": "admin_stats"}],
            [{"text": "🔙 Назад", "callback_data": "back"}]
        ]
    }

def back_button():
    return {"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back"}]]}

# ===== ОБРАБОТЧИКИ =====
def handle_start(chat_id, username):
    add_user(chat_id, username)
    send_message(chat_id, 
                 "🔥 *PlutoniumDLL* — лучший софт для Standoff 2!\nВыберите действие:",
                 main_menu())

def handle_callback(callback):
    data = callback["data"]
    chat_id = callback["from"]["id"]
    msg_id = callback["message"]["message_id"]
    username = callback["from"].get("username", "NoName")

    if data == "back":
        edit_message(chat_id, msg_id, "🔥 Главное меню:", main_menu())
        answer_callback(callback["id"])
        return

    if data == "buy":
        edit_message(chat_id, msg_id, "💰 *Выберите тариф:*\n\n⭐ 7д — 50\n⭐ 30д — 250\n⭐ 90д — 500\n⭐ Навсегда — 600", tariffs_menu())
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
            edit_message(chat_id, msg_id, "❌ Промо-коды кончились. Напишите @oryke или @shezik", 
                        {"inline_keyboard": [[{"text": "🆘 Поддержка", "callback_data": "support"}]]})
            answer_callback(callback["id"])
            return
        
        result = send_invoice(chat_id, tariff_name, price, promo)
        if result.get("ok"):
            answer_callback(callback["id"], "💳 Счёт отправлен!")
        else:
            edit_message(chat_id, msg_id, f"❌ Ошибка: {result.get('description')}", back_button())
            answer_callback(callback["id"])
        return

    if data == "my_subs":
        purchases = get_user_purchases(chat_id)
        if not purchases:
            text = "❌ Нет активных подписок."
            kb = {"inline_keyboard": [[{"text": "💰 Купить", "callback_data": "buy"}], [{"text": "🔙 Назад", "callback_data": "back"}]]}
        else:
            text = "📋 *Ваши подписки:*\n\n"
            for tariff, promo, date in purchases:
                text += f"• {tariff} — `{promo}`\n"
            kb = back_button()
        edit_message(chat_id, msg_id, text, kb)
        answer_callback(callback["id"])
        return

    if data == "support":
        edit_message(chat_id, msg_id, 
                     "🆘 *Поддержка:*\n@oryke — техподдержка\n@shezik — оплата",
                     back_button())
        answer_callback(callback["id"])
        return

    if data == "stats":
        total_users, total_purchases, total_stars, free_promos = get_stats()
        text = f"📊 *Статистика:*\n👥 {total_users}\n💳 {total_purchases}\n⭐ {total_stars}\n🎫 Свободных промо: {free_promos}"
        edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

    if data == "admin":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа", True)
            return
        edit_message(chat_id, msg_id, "⚙️ *Админ-панель*", admin_menu())
        answer_callback(callback["id"])
        return

    # Админские действия
    if data == "add_promo":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа", True)
            return
        edit_message(chat_id, msg_id, "Используйте команду /addpromo КОЛИЧЕСТВО или /addpromo КОД1,КОД2", back_button())
        answer_callback(callback["id"])
        return

    if data == "del_promo":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа", True)
            return
        edit_message(chat_id, msg_id, "Используйте /delpromo КОД", back_button())
        answer_callback(callback["id"])
        return

    if data == "list_promo":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа", True)
            return
        promos = get_all_promos()
        text = "📦 *Промо-коды:*\n"
        for code, used, used_by in promos:
            status = "❌" if used else "✅"
            text += f"{status} `{code}`" + (f" (user {used_by})" if used_by else "") + "\n"
        edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

    if data == "list_users":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа", True)
            return
        users = get_all_users()
        text = "👥 *Пользователи:*\n"
        for uid, uname, spent, reg in users:
            text += f"• {uname} ({uid}) — {spent}⭐, рег: {reg[:10]}\n"
        edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

    if data == "admin_stats":
        if chat_id not in ADMIN_IDS:
            answer_callback(callback["id"], "⛔ Нет доступа", True)
            return
        total_users, total_purchases, total_stars, free_promos = get_stats()
        text = f"📈 *Полная статистика:*\n👥 {total_users}\n💳 {total_purchases}\n⭐ {total_stars}\n🎫 Свободных: {free_promos}"
        edit_message(chat_id, msg_id, text, back_button())
        answer_callback(callback["id"])
        return

def handle_message(chat_id, text, username):
    add_user(chat_id, username)

    # ===== АДМИН-КОМАНДЫ =====
    if text.startswith("/addpromo"):
        if chat_id not in ADMIN_IDS:
            send_message(chat_id, "⛔ Нет прав")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "❌ Пример: /addpromo 5  или  /addpromo CODE1,CODE2")
            return
        arg = parts[1].strip()
        if arg.isdigit():
            count = int(arg)
            codes = [''.join(random.choices(string.ascii_uppercase + string.digits, k=12)) for _ in range(count)]
            added = add_promo_codes(codes)
            send_message(chat_id, f"✅ Добавлено {added} промо-кодов.")
        else:
            codes = [c.strip() for c in arg.split(",") if c.strip()]
            added = add_promo_codes(codes)
            send_message(chat_id, f"✅ Добавлено {added} промо-кодов.")
        return

    if text.startswith("/delpromo"):
        if chat_id not in ADMIN_IDS:
            send_message(chat_id, "⛔ Нет прав")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "❌ Пример: /delpromo ABC123")
            return
        code = parts[1].strip()
        if delete_promo(code):
            send_message(chat_id, f"✅ Код {code} удалён.")
        else:
            send_message(chat_id, f"❌ Код {code} не найден.")
        return

    # ===== КОМАНДА /crack =====
    if text.startswith("/crack"):
        purchases = get_user_purchases(chat_id)
        if not purchases:
            send_message(chat_id, 
                         "❌ *Доступ закрыт.*\nУ вас нет активной подписки.\nКупите доступ: /pay",
                         {"inline_keyboard": [[{"text": "💰 Купить", "callback_data": "buy"}]]})
            return
        last_promo = purchases[0][1]
        send_message(chat_id,
                     f"✅ *Доступ открыт!*\n\n🎫 Ваш промо-код: `{last_promo}`\n🔗 Активация: https://plut.cc\n📧 Вопросы: @oryke",
                     parse_mode="Markdown")
        return

    # ===== КОМАНДА /pay =====
    if text == "/pay":
        send_message(chat_id, "💰 *Выберите тариф:*", tariffs_menu())
        return

    # ===== КОМАНДА /price =====
    if text == "/price":
        send_message(chat_id,
                     "📋 *Прайс-лист:*\n\n7 дней — 50 ⭐\n30 дней — 250 ⭐\n90 дней — 500 ⭐\nНавсегда — 600 ⭐\n\nДля покупки: /pay",
                     back_button())
        return

    # ===== КОМАНДА /functions =====
    if text == "/functions":
        send_message(chat_id,
                     "📌 *Список команд:*\n\n/start — Главное меню\n/pay — Купить подписку\n/price — Прайс-лист\n/crack — Получить промо-код (нужен доступ)\n/functions — Этот список\n\n🔹 *Админ-команды:*\n/addpromo N — добавить N промо\n/addpromo CODE1,CODE2 — добавить конкретные\n/delpromo CODE — удалить промо",
                     back_button())
        return

    # Если неизвестная команда — отправляем главное меню
    send_message(chat_id, "Используйте кнопки или /start", main_menu())

def handle_successful_payment(chat_id, payload, total_amount):
    tariff_name, promo_code = payload.split("|")
    use_promo(promo_code, chat_id)
    add_purchase(chat_id, tariff_name, total_amount, promo_code)
    send_message(chat_id, 
                 f"✅ *Оплата подтверждена!*\n\nТариф: {tariff_name}\nВаш промо-код:\n`{promo_code}`\n\nАктивация на https://plut.cc", 
                 back_button())
    # Уведомление админам
    for admin in ADMIN_IDS:
        send_message(admin, f"💰 Новая покупка!\nПользователь: {chat_id}\nТариф: {tariff_name}\nПромо: {promo_code}")
