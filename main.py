import os
import sys
import json
import sqlite3
import re
import hashlib
import logging
import requests
import random
import string
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ==========================
# 0. КОНФИГУРАЦИЯ
# ==========================
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_IDS = [8428048355]
DATA_FILE = "data.json"
DEFAULT_QUERIES = 5

logging.basicConfig(level=logging.INFO)

users: Dict[int, Dict] = {}
checks: Dict[str, Dict] = {}
banned_users: set = set()
banned_ips: set = set()
user_ips: Dict[int, str] = {}

# ==========================
# 1. РАБОТА С ДАННЫМИ
# ==========================
def load_data():
    global users, checks, banned_users, banned_ips, user_ips
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                users = {int(k): v for k, v in data.get("users", {}).items()}
                checks = data.get("checks", {})
                banned_users = set(data.get("banned_users", []))
                banned_ips = set(data.get("banned_ips", []))
                user_ips = {int(k): v for k, v in data.get("user_ips", {}).items()}
        except Exception:
            pass

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "users": {str(k): v for k, v in users.items()},
                "checks": checks,
                "banned_users": list(banned_users),
                "banned_ips": list(banned_ips),
                "user_ips": {str(k): v for k, v in user_ips.items()}
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

load_data()

def get_user_queries(user_id: int) -> int:
    return users.get(user_id, {}).get("queries", 0)

def add_queries(user_id: int, amount: int):
    if user_id not in users:
        users[user_id] = {
            "queries": 0,
            "username": str(user_id),
            "first_name": "Пользователь",
            "registered": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
    users[user_id]["queries"] += amount
    save_data()

def use_query(user_id: int) -> bool:
    if user_id in banned_users:
        return False
    if users.get(user_id, {}).get("queries", 0) > 0:
        users[user_id]["queries"] -= 1
        save_data()
        return True
    return False

def get_user_identifier(user_id: int) -> str:
    data = users.get(user_id, {})
    username = data.get("username")
    first_name = data.get("first_name", "Пользователь")
    return f"@{username}" if username and username != str(user_id) else first_name

def generate_code(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def get_user_ip(user_id: int) -> str:
    return user_ips.get(user_id, "Неизвестно")

def set_user_ip(user_id: int, ip: str):
    user_ips[user_id] = ip
    save_data()

def is_banned(user_id: int, ip: Optional[str] = None) -> bool:
    if user_id in banned_users:
        return True
    if ip and ip in banned_ips:
        return True
    return False

def find_user_by_username(username: str) -> Optional[int]:
    username = username.replace("@", "")
    for uid, data in users.items():
        if data.get("username") == username:
            return uid
    return None

# ==========================
# 2. КЛАВИАТУРА
# ==========================
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск", callback_data="search")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("✅ Чекки", callback_data="checks")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])

# ==========================
# 3. БАЗЫ ДАННЫХ (АВТОЗАГРУЗКА)
# ==========================
def create_egrn_database():
    db_path = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(db_path):
        os.makedirs(db_path)
    db_file = os.path.join(db_path, "egrn.db")
    if os.path.exists(db_file) and os.path.getsize(db_file) > 1024 * 1024 * 5:
        return
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS egrn (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            address TEXT,
            cadastral_number TEXT,
            area REAL,
            ownership_type TEXT,
            registration_date TEXT,
            passport_series TEXT,
            passport_number TEXT,
            inn TEXT,
            snils TEXT,
            phone TEXT,
            email TEXT,
            birth_date TEXT,
            birth_place TEXT,
            source TEXT
        )
    ''')
    people_data = [
        ("Иванов Иван Иванович", "г. Москва, ул. Тверская, д. 1, кв. 5", "77:01:0000000:1", 45.2, "Собственность", "15.03.2020", "45", "1234567", "123456789012", "12345678901", "+79001234567", "ivanov.ivan@mail.ru", "15.03.1990", "г. Москва", "Публичный реестр"),
        ("Петров Петр Петрович", "г. Москва, ул. Арбат, д. 2, кв. 10", "77:01:0000000:2", 32.5, "Собственность", "20.05.2020", "45", "7654321", "987654321098", "98765432109", "+79009876543", "petrov.petr@mail.ru", "20.05.1985", "г. Санкт-Петербург", "Публичный реестр"),
        ("Сидоров Сидор Сидорович", "г. Москва, ул. Пушкинская, д. 3, кв. 15", "77:01:0000000:3", 78.0, "Долевая собственность", "10.07.2020", "45", "1111111", "111111111111", "11111111111", "+79001111111", "sidorov.sidor@mail.ru", "10.07.1988", "г. Казань", "Публичный реестр"),
        ("Кузнецов Алексей Петрович", "г. Москва, ул. Горького, д. 5, кв. 8", "77:01:0000000:5", 55.0, "Собственность", "12.11.2020", "45", "3333333", "333333333333", "33333333333", "+79003333333", "kuznecov.alexey@mail.ru", "12.11.1982", "г. Екатеринбург", "Публичный реестр"),
        ("Смирнов Дмитрий Васильевич", "г. Москва, ул. Садовая, д. 6, кв. 12", "77:01:0000000:6", 42.3, "Собственность", "23.12.2020", "45", "4444444", "444444444444", "44444444444", "+79004444444", "smirnov.dmitry@mail.ru", "23.12.1979", "г. Новосибирск", "Публичный реестр"),
        ("Дуров Павел Валерьевич", "г. Москва, ул. Ленинградская, д. 10, кв. 20", "77:01:0000000:10", 120.5, "Собственность", "01.01.2020", "40", "1234567", "123456789012", "12345678901", "+79000000001", "durov@telegram.org", "10.10.1984", "г. Ленинград", "Публичный реестр"),
        ("Морозов Александр Сергеевич", "г. Москва, ул. Мира, д. 7, кв. 8", "77:01:0000000:7", 38.7, "Собственность", "04.02.2021", "45", "5555555", "555555555555", "55555555555", "+79005555555", "morozov.alexander@mail.ru", "04.02.1987", "г. Красноярск", "Публичный реестр"),
        ("Волков Алексей Владимирович", "г. Москва, ул. Молодежная, д. 8, кв. 3", "77:01:0000000:8", 50.0, "Собственность", "17.03.2021", "45", "6666666", "666666666666", "66666666666", "+79006666666", "volkov.alexey@mail.ru", "17.03.1992", "г. Казань", "Публичный реестр"),
        ("Соколов Михаил Иванович", "г. Москва, ул. Парковая, д. 9, кв. 6", "77:01:0000000:9", 63.8, "Долевая собственность", "28.04.2021", "45", "7777777", "777777777777", "77777777777", "+79007777777", "sokolov.mikhail@mail.ru", "28.04.1981", "г. Санкт-Петербург", "Публичный реестр"),
    ]
    for person in people_data:
        c.execute('''
            INSERT INTO egrn (full_name, address, cadastral_number, area, ownership_type, registration_date,
                              passport_series, passport_number, inn, snils, phone, email, birth_date, birth_place, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', person)
    conn.commit()
    conn.close()
    logging.info("База ЕГРН создана.")

create_egrn_database()

# ==========================
# 4. ПОИСК ПО БАЗАМ
# ==========================
def search_all_databases(query: str) -> Dict:
    result = {
        "full_name": None,
        "address": None,
        "birth_date": None,
        "birth_place": None,
        "passport_series": None,
        "passport_number": None,
        "inn": None,
        "snils": None,
        "phone": None,
        "email": None,
        "social": [],
        "source": "База данных",
        "cadastral_number": None,
        "area": None,
        "ownership_type": None,
        "registration_date": None,
    }
    try:
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "data", "egrn.db"))
        c = conn.cursor()
        c.execute('''
            SELECT full_name, address, cadastral_number, area, ownership_type, registration_date,
                   passport_series, passport_number, inn, snils, phone, email, birth_date, birth_place, source
            FROM egrn
            WHERE full_name LIKE ? OR address LIKE ? OR phone LIKE ? OR email LIKE ? OR cadastral_number LIKE ?
            LIMIT 1
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
        row = c.fetchone()
        if row:
            result["full_name"] = row[0]
            result["address"] = row[1]
            result["cadastral_number"] = row[2]
            result["area"] = row[3]
            result["ownership_type"] = row[4]
            result["registration_date"] = row[5]
            result["passport_series"] = row[6]
            result["passport_number"] = row[7]
            result["inn"] = row[8]
            result["snils"] = row[9]
            result["phone"] = row[10]
            result["email"] = row[11]
            result["birth_date"] = row[12]
            result["birth_place"] = row[13]
            result["source"] = row[14]
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка поиска в базе: {e}")
    return result

def search_social_media(query: str) -> List[str]:
    result = []
    nick = query.replace(" ", "_")
    platforms = {
        "VK": f"https://vk.com/{nick}",
        "Telegram": f"https://t.me/{nick}",
        "Instagram": f"https://instagram.com/{nick}",
        "GitHub": f"https://github.com/{nick}",
        "Twitter": f"https://twitter.com/{nick}",
        "TikTok": f"https://tiktok.com/@{nick}",
        "YouTube": f"https://youtube.com/@{nick}"
    }
    for name, url in platforms.items():
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200:
                result.append(f"✅ {name}: {url}")
        except:
            pass
    return result

def search_vk(query: str) -> List[str]:
    result = []
    try:
        vk_api = f"https://api.vk.com/method/users.search?q={query}&count=3&v=5.131"
        r = requests.get(vk_api, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "response" in data and data["response"]["count"] > 0:
                for user in data["response"]["items"]:
                    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    city = user.get("city", {}).get("title", "Неизвестно")
                    result.append(f"✅ VK: https://vk.com/id{user['id']} ({name}, {city})")
    except:
        pass
    return result

def check_breaches(email: str) -> int:
    try:
        sha1 = hashlib.sha1(email.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        r = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
        for line in r.text.splitlines():
            if line.startswith(suffix):
                return int(line.split(":")[1])
    except:
        pass
    return 0

def get_ip_info(ip: str) -> Optional[Dict]:
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def search_by_phone(phone: str) -> List[str]:
    result = []
    clean_phone = phone.replace(" ", "").replace("-", "")
    result.append(f"📱 Telegram: https://t.me/+{clean_phone}")
    result.append(f"💬 WhatsApp: https://wa.me/{clean_phone}")
    result.append(f"💬 Viber: https://chats.viber.com/{clean_phone}")
    return result

# ==========================
# 5. ОСНОВНАЯ ЛОГИКА ПОИСКА
# ==========================
async def smart_search(query: str, user_id: int) -> Dict:
    if is_banned(user_id):
        return {"personal": {"Ошибка": "❌ Вы были заблокированы администратором."}}

    result = {
        "personal": {},
        "phone": None,
        "email": None,
        "social": [],
        "breaches": 0,
        "source": None,
        "cadastral_number": None,
        "area": None,
        "ownership_type": None,
        "registration_date": None,
    }

    # 1. Поиск в базе
    db_result = search_all_databases(query)
    if db_result.get("full_name"):
        if db_result.get("full_name"):
            result["personal"]["ФИО"] = db_result["full_name"]
        if db_result.get("address"):
            result["personal"]["Адрес"] = db_result["address"]
        if db_result.get("birth_date"):
            result["personal"]["Дата рождения"] = db_result["birth_date"]
        if db_result.get("birth_place"):
            result["personal"]["Место рождения"] = db_result["birth_place"]
        if db_result.get("passport_series") and db_result.get("passport_number"):
            result["personal"]["Паспорт"] = f"{db_result['passport_series']} {db_result['passport_number']}"
        if db_result.get("inn"):
            result["personal"]["ИНН"] = db_result["inn"]
        if db_result.get("snils"):
            result["personal"]["СНИЛС"] = db_result["snils"]
        if db_result.get("phone"):
            result["phone"] = db_result["phone"]
            result["personal"]["Телефон"] = db_result["phone"]
        if db_result.get("email"):
            result["email"] = db_result["email"]
            result["personal"]["Email"] = db_result["email"]
        if db_result.get("source"):
            result["source"] = db_result["source"]
        if db_result.get("cadastral_number"):
            result["cadastral_number"] = db_result["cadastral_number"]
            result["personal"]["Кадастровый номер"] = db_result["cadastral_number"]
        if db_result.get("area"):
            result["area"] = db_result["area"]
            result["personal"]["Площадь"] = f"{db_result['area']} м²"
        if db_result.get("ownership_type"):
            result["ownership_type"] = db_result["ownership_type"]
            result["personal"]["Вид права"] = db_result["ownership_type"]
        if db_result.get("registration_date"):
            result["registration_date"] = db_result["registration_date"]
            result["personal"]["Дата регистрации"] = db_result["registration_date"]
        return result

    # 2. Телефон
    if re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query):
        phone = re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query).group(0).replace(" ", "").replace("-", "")
        result["phone"] = phone
        phone_results = search_by_phone(phone)
        result["social"].extend(phone_results)
        return result

    # 3. IP
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', query):
        ip_data = get_ip_info(query)
        if ip_data and ip_data.get("status") == "success":
            result["personal"]["IP"] = query
            result["personal"]["Город"] = ip_data.get("city", "Неизвестно")
            result["personal"]["Регион"] = ip_data.get("regionName", "Неизвестно")
            result["personal"]["Страна"] = ip_data.get("country", "Неизвестно")
            result["personal"]["Провайдер"] = ip_data.get("isp", "Неизвестно")
            return result
        result["personal"]["Ошибка"] = "Не удалось получить данные по IP"
        return result

    # 4. Email
    if '@' in query:
        email = query.strip()
        result["email"] = email
        breaches = check_breaches(email)
        if breaches > 0:
            result["breaches"] = breaches
            result["personal"]["Утечки"] = f"{breaches} утечек"
        else:
            result["personal"]["Утечки"] = "Не найден в утечках"
        return result

    # 5. Юзернейм Telegram
    if query.startswith("@"):
        username = query[1:]
        result["personal"]["Ник"] = f"@{username}"
        social_results = search_social_media(username)
        if social_results:
            result["social"].extend(social_results)
        return result

    # 6. ФИО (поиск в соцсетях)
    if len(query.split()) >= 2:
        vk_results = search_vk(query)
        if vk_results:
            result["social"].extend(vk_results)
        social_results = search_social_media(query.replace(" ", "_"))
        if social_results:
            result["social"].extend(social_results)
        return result

    # 7. Ничего не найдено
    if not result["personal"] and not result["social"]:
        result["personal"]["Информация"] = "❌ Ничего не найдено. Попробуйте уточнить запрос."

    return result

def generate_html_report(query: str, user_id: int, username: str, data: Dict) -> Tuple[str, str]:
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    filename = f"search_{user_id}_{datetime.now().strftime('%d%m%y_%H%M%S')}.html"

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OSINT Report - {query}</title>
    <style>
        body {{ font-family: 'Courier New', monospace; background: #0d0d0d; color: #00ffcc; padding: 20px; }}
        .header {{ color: #ff3366; font-size: 28px; font-weight: bold; border-bottom: 2px solid #ff3366; padding-bottom: 10px; }}
        .sub {{ color: #888; font-size: 14px; margin-top: 5px; }}
        .category {{ color: #ffcc00; font-size: 22px; margin-top: 30px; border-bottom: 1px solid #333; }}
        .item {{ color: #00ffcc; margin-left: 20px; }}
        .tag {{ color: #ff6699; }}
        .footer {{ margin-top: 40px; color: #555; font-size: 12px; border-top: 1px solid #222; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">🌙 MOON DATA | Smertnyy Search</div>
    <div class="sub">Запрос: {query}</div>
    <div class="sub">Пользователь: @{username} (ID: {user_id})</div>
    <div class="sub">Дата: {now}</div>
    <div class="category">📌 ЛИЧНЫЕ ДАННЫЕ</div>
'''
    if data.get("personal"):
        order = ["ФИО", "Адрес", "Дата рождения", "Место рождения", "Паспорт", "ИНН", "СНИЛС", "Телефон", "Email", "Утечки", "Кадастровый номер", "Площадь", "Вид права", "Дата регистрации", "Ник", "IP", "Город", "Регион", "Страна", "Провайдер"]
        for key in order:
            if key in data["personal"]:
                html += f'    <div class="item">{key}: {data["personal"][key]}</div>\n'
        for k, v in data["personal"].items():
            if k not in order:
                html += f'    <div class="item">{k}: {v}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">🔗 СОЦИАЛЬНЫЕ СЕТИ И ССЫЛКИ</div>
'''
    if data.get("social"):
        for soc in data["social"][:20]:
            html += f'    <div class="item">{soc}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">📡 ИСТОЧНИК</div>
'''
    if data.get("source"):
        html += f'    <div class="item">✅ {data["source"]}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="footer">Источники: Локальная база ЕГРН, VK API, Google, HaveIBeenPwned, ip-api.com</div>
    <div class="footer">🌙 Smertnyy Search — ваш надёжный OSINT-инструмент</div>
</body>
</html>
'''
    return html, filename

# ==========================
# 6. ОБРАБОТЧИКИ КОМАНД
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    first_name = update.effective_user.first_name or "Пользователь"
    ip = update.effective_user.link or "Неизвестно"
    set_user_ip(user_id, ip)

    if is_banned(user_id, ip):
        await update.message.reply_text("❌ Вы были заблокированы администратором.")
        return

    if user_id not in users:
        users[user_id] = {
            "queries": DEFAULT_QUERIES,
            "username": username,
            "first_name": first_name,
            "registered": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        save_data()

    balance = get_user_queries(user_id)
    await update.message.reply_text(
        f"👋 Добро пожаловать в *Smertnyy Search*, {get_user_identifier(user_id)}!\n"
        f"📊 Осталось запросов: {balance}\n\n"
        f"🔍 Введите:\n"
        f"• 👤 ФИО — полный пробив по ЕГРН\n"
        f"• 📱 Номер телефона — соцсети\n"
        f"• 🆔 Ник Telegram — ID и соцсети\n"
        f"• 🌐 IP-адрес — геолокация\n"
        f"• 📧 Email — утечки\n\n"
        f"📌 Бот использует базу ЕГРН, VK, Telegram, Instagram, GitHub, HaveIBeenPwned, ip-api.com",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без ника"
    ip = update.effective_user.link or "Неизвестно"
    set_user_ip(user_id, ip)

    if is_banned(user_id, ip):
        await update.message.reply_text("❌ Вы были заблокированы администратором.")
        return

    text = update.message.text.strip()

    if get_user_queries(user_id) <= 0:
        await update.message.reply_text("❌ Закончились запросы.", reply_markup=main_menu())
        return

    if not use_query(user_id):
        await update.message.reply_text("❌ Ошибка.", reply_markup=main_menu())
        return

    search_msg = await update.message.reply_text("⏳ Поиск...", reply_markup=None)

    try:
        data = await smart_search(text, user_id)
        html, filename = generate_html_report(text, user_id, username, data)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        msg = "📊 *Результаты поиска*\n\n"
        if data.get("personal"):
            for k, v in data["personal"].items():
                if k != "Ошибка":
                    msg += f"👤 *{k}:* {v}\n"
            if "Ошибка" in data["personal"]:
                msg += f"❌ {data['personal']['Ошибка']}\n"

        if data.get("phone"):
            msg += f"\n📱 *Телефон:* `{data['phone']}`\n"
        if data.get("email"):
            msg += f"\n📧 *Email:* `{data['email']}`\n"
        if data.get("breaches") and data["breaches"] > 0:
            msg += f"🔴 *Утечки:* {data['breaches']}\n"

        if data.get("social"):
            msg += f"\n🔗 *Соцсети ({len(data['social'])}):*\n"
            for soc in data["social"][:5]:
                msg += f"  • {soc}\n"
            if len(data["social"]) > 5:
                msg += f"  ... и ещё {len(data['social']) - 5}\n"

        if data.get("source"):
            msg += f"\n📡 *Источник:* {data['source']}"

        if not data.get("personal") and not data.get("phone") and not data.get("email") and not data.get("social"):
            msg = "❌ Ничего не найдено."

        msg += f"\n\n📄 *HTML-отчёт приложен*"

        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename=filename),
                caption=msg,
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        os.remove(filename)
        await search_msg.delete()

    except Exception as e:
        add_queries(user_id, 1)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=main_menu())
        await search_msg.delete()

# ==========================
# 7. КОЛБЭКИ МЕНЮ
# ==========================
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        balance = get_user_queries(user_id)
        await query.edit_message_text(
            f"👋 Главное меню\n📊 Осталось запросов: {balance}",
            reply_markup=main_menu()
        )
    elif data == "search":
        await query.edit_message_text(
            "🔍 *Поиск*\n\n"
            "Отправьте мне:\n"
            "• 👤 ФИО\n"
            "• 📱 Номер телефона\n"
            "• 🆔 Ник Telegram\n"
            "• 🌐 IP-адрес\n"
            "• 📧 Email",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "profile":
        balance = get_user_queries(user_id)
        registered = users.get(user_id, {}).get("registered", "Неизвестно")
        ip = get_user_ip(user_id)
        await query.edit_message_text(
            f"👤 *Профиль*\n\n"
            f"🆔 ID: {user_id}\n"
            f"📊 Осталось запросов: {balance}\n"
            f"📅 Регистрация: {registered}\n"
            f"🌐 IP: {ip}",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "checks":
        await query.edit_message_text(
            "✅ *Доступные чекки*\n\n"
            "• 👤 ФИО — полный пробив (ЕГРН, паспорт, ИНН, СНИЛС)\n"
            "• 📱 Телефон — соцсети\n"
            "• 🆔 Ник — ID и соцсети\n"
            "• 🌐 IP — геолокация\n"
            "• 📧 Email — утечки",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "support":
        await query.edit_message_text("🆘 Владелец: @okimdeadlybutimnotteamsandidmeok", reply_markup=back_button())
    elif data == "admin":
        await query.edit_message_text(
            "⚙️ *Админ-панель*\n\n"
            "/give @username кол-во\n"
            "/steal @username кол-во\n"
            "/deletecheck КОД\n"
            "/block @username\n"
            "/blockip @username\n"
            "/unblock @username\n"
            "/unblockip @username\n"
            "/banlist\n"
            "/iplist\n"
            "/setlimit количество\n"
            "/broadcast сообщение\n"
            "/createcheck Название запросы активации",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )

# ==========================
# 8. АДМИН-КОМАНДЫ
# ==========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def give_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ /give @username кол-во")
        return
    target = args[0].replace("@", "")
    try:
        amount = int(args[1])
    except:
        await update.message.reply_text("❌ Число")
        return
    uid = find_user_by_username(target)
    if not uid:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    add_queries(uid, amount)
    await update.message.reply_text(f"✅ Выдано {amount} запросов пользователю {target}")

async def steal_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ /steal @username кол-во")
        return
    target = args[0].replace("@", "")
    try:
        amount = int(args[1])
    except:
        await update.message.reply_text("❌ Число")
        return
    uid = find_user_by_username(target)
    if not uid:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    if users[uid]["queries"] < amount:
        await update.message.reply_text("❌ У пользователя недостаточно запросов")
        return
    users[uid]["queries"] -= amount
    save_data()
    await update.message.reply_text(f"✅ Забрано {amount} запросов у {target}")

async def delete_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /deletecheck КОД")
        return
    code = args[0].upper()
    if code not in checks:
        await update.message.reply_text("❌ Чек не найден")
        return
    del checks[code]
    save_data()
    await update.message.reply_text(f"✅ Чек {code} удалён")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /block @username")
        return
    target = args[0].replace("@", "")
    uid = find_user_by_username(target)
    if not uid:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    banned_users.add(uid)
    save_data()
    await update.message.reply_text(f"✅ Пользователь {target} заблокирован")

async def block_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /blockip @username")
        return
    target = args[0].replace("@", "")
    uid = find_user_by_username(target)
    if not uid:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    ip = get_user_ip(uid)
    if ip != "Неизвестно":
        banned_ips.add(ip)
        save_data()
        await update.message.reply_text(f"✅ IP {ip} пользователя {target} заблокирован")
    else:
        await update.message.reply_text("❌ IP пользователя не найден")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /unblock @username")
        return
    target = args[0].replace("@", "")
    uid = find_user_by_username(target)
    if not uid:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    if uid in banned_users:
        banned_users.remove(uid)
        save_data()
        await update.message.reply_text(f"✅ Пользователь {target} разблокирован")
    else:
        await update.message.reply_text("❌ Пользователь не был заблокирован")

async def unblock_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /unblockip @username")
        return
    target = args[0].replace("@", "")
    uid = find_user_by_username(target)
    if not uid:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    ip = get_user_ip(uid)
    if ip in banned_ips:
        banned_ips.remove(ip)
        save_data()
        await update.message.reply_text(f"✅ IP {ip} пользователя {target} разблокирован")
    else:
        await update.message.reply_text("❌ IP не был заблокирован")

async def banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not banned_users:
        await update.message.reply_text("📊 Список заблокированных пользователей пуст")
        return
    msg = "📊 *Заблокированные пользователи:*\n"
    for uid in banned_users:
        username = users.get(uid, {}).get("username", str(uid))
        msg += f"• {username}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def iplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not banned_ips:
        await update.message.reply_text("📊 Список заблокированных IP пуст")
        return
    msg = "📊 *Заблокированные IP:*\n"
    for ip in banned_ips:
        msg += f"• {ip}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /setlimit количество")
        return
    try:
        limit = int(args[0])
    except:
        await update.message.reply_text("❌ Введите число")
        return
    global DEFAULT_QUERIES
    DEFAULT_QUERIES = limit
    await update.message.reply_text(f"✅ Лимит запросов для новых пользователей установлен на {limit}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /broadcast сообщение")
        return
    msg = " ".join(args)
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 *Сообщение от администратора:*\n{msg}", parse_mode="Markdown")
        except:
            pass
    await update.message.reply_text("✅ Сообщение отправлено всем пользователям")

async def create_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ /createcheck Название запросы активации")
        return
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    checks[code] = {"queries": int(args[1]), "activations": int(args[2]), "used_by": []}
    save_data()
    await update.message.reply_text(f"✅ Чек {code} создан.\n📊 {args[1]} запросов, {args[2]} активаций.")

async def activate_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("❌ /activate КОД")
        return
    code = args[0].upper()
    if code not in checks:
        await update.message.reply_text("❌ Неверный код")
        return
    check = checks[code]
    if user_id in check.get("used_by", []):
        await update.message.reply_text("❌ Вы уже активировали этот чек")
        return
    if check["activations"] <= 0:
        await update.message.reply_text("❌ Чек использован")
        return
    add_queries(user_id, check["queries"])
    check["used_by"].append(user_id)
    check["activations"] -= 1
    if check["activations"] == 0:
        del checks[code]
    save_data()
    await update.message.reply_text(f"✅ +{check['queries']} запросов")

# ==========================
# 9. ЗАПУСК
# ==========================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("give", give_queries))
    app.add_handler(CommandHandler("steal", steal_queries))
    app.add_handler(CommandHandler("deletecheck", delete_check))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("blockip", block_ip))
    app.add_handler(CommandHandler("unblock", unblock_user))
    app.add_handler(CommandHandler("unblockip", unblock_ip))
    app.add_handler(CommandHandler("banlist", banlist))
    app.add_handler(CommandHandler("iplist", iplist))
    app.add_handler(CommandHandler("setlimit", set_limit))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("createcheck", create_check))
    app.add_handler(CommandHandler("activate", activate_check))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Smertnyy Search (полный пробив) запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
