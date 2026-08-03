import logging
import re
import requests
import random
import string
import json
import os
import hashlib
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== КОНФИГ =====
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_IDS = [8428048355]
DATA_FILE = "data.json"
DEFAULT_QUERIES = 5

logging.basicConfig(level=logging.INFO)

users = {}
checks = {}
banned_users = set()
banned_ips = set()
user_ips = {}

# ===== ФУНКЦИИ РАБОТЫ С ДАННЫМИ =====
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
        except:
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
    except:
        pass

load_data()

def get_user_queries(user_id):
    return users.get(user_id, {}).get("queries", 0)

def add_queries(user_id, amount):
    if user_id not in users:
        users[user_id] = {"queries": 0, "username": str(user_id), "first_name": "Пользователь", "registered": datetime.now().strftime("%d.%m.%Y %H:%M")}
    users[user_id]["queries"] += amount
    save_data()

def use_query(user_id):
    if user_id in banned_users:
        return False
    if users.get(user_id, {}).get("queries", 0) > 0:
        users[user_id]["queries"] -= 1
        save_data()
        return True
    return False

def get_user_identifier(user_id):
    data = users.get(user_id, {})
    username = data.get("username")
    first_name = data.get("first_name", "Пользователь")
    return f"@{username}" if username and username != str(user_id) else first_name

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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

def get_user_ip(user_id):
    return user_ips.get(user_id, "Неизвестно")

def set_user_ip(user_id, ip):
    user_ips[user_id] = ip
    save_data()

def is_banned(user_id, ip=None):
    if user_id in banned_users:
        return True
    if ip and ip in banned_ips:
        return True
    return False

def find_user_by_username(username):
    username = username.replace("@", "")
    for uid, data in users.items():
        if data.get("username") == username:
            return uid
    return None

# ===== СОЗДАНИЕ БАЗЫ ДАННЫХ =====
def create_database():
    """Создает все необходимые базы данных"""
    db_path = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(db_path):
        os.makedirs(db_path)
    
    db_file = os.path.join(db_path, "egrn.db")
    if os.path.exists(db_file):
        return
    
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    # Таблица ЕГРН
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
            birth_place TEXT
        )
    ''')
    
    # Таблица паспортных данных
    c.execute('''
        CREATE TABLE IF NOT EXISTS passports (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            passport_series TEXT,
            passport_number TEXT,
            issued_by TEXT,
            issue_date TEXT,
            birth_date TEXT,
            birth_place TEXT
        )
    ''')
    
    # Таблица телефонов
    c.execute('''
        CREATE TABLE IF NOT EXISTS phones (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone TEXT,
            source TEXT
        )
    ''')
    
    # Таблица ИНН и СНИЛС
    c.execute('''
        CREATE TABLE IF NOT EXISTS snils_inn (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            inn TEXT,
            snils TEXT
        )
    ''')
    
    # === НАПОЛНЯЕМ БАЗУ ДАННЫМИ ===
    people_data = [
        {
            "full_name": "Иванов Иван Иванович",
            "address": "г. Москва, ул. Тверская, д. 1, кв. 5",
            "cadastral_number": "77:01:0000000:1",
            "area": 45.2,
            "ownership_type": "Собственность",
            "registration_date": "15.03.2020",
            "passport_series": "45",
            "passport_number": "1234567",
            "inn": "123456789012",
            "snils": "12345678901",
            "phone": "+79001234567",
            "email": "ivanov.ivan@mail.ru",
            "birth_date": "15.03.1990",
            "birth_place": "г. Москва"
        },
        {
            "full_name": "Петров Петр Петрович",
            "address": "г. Москва, ул. Арбат, д. 2, кв. 10",
            "cadastral_number": "77:01:0000000:2",
            "area": 32.5,
            "ownership_type": "Собственность",
            "registration_date": "20.05.2020",
            "passport_series": "45",
            "passport_number": "7654321",
            "inn": "987654321098",
            "snils": "98765432109",
            "phone": "+79009876543",
            "email": "petrov.petr@mail.ru",
            "birth_date": "20.05.1985",
            "birth_place": "г. Санкт-Петербург"
        },
        {
            "full_name": "Сидоров Сидор Сидорович",
            "address": "г. Москва, ул. Пушкинская, д. 3, кв. 15",
            "cadastral_number": "77:01:0000000:3",
            "area": 78.0,
            "ownership_type": "Долевая собственность",
            "registration_date": "10.07.2020",
            "passport_series": "45",
            "passport_number": "1111111",
            "inn": "111111111111",
            "snils": "11111111111",
            "phone": "+79001111111",
            "email": "sidorov.sidor@mail.ru",
            "birth_date": "10.07.1988",
            "birth_place": "г. Казань"
        },
        {
            "full_name": "Кузнецов Алексей Петрович",
            "address": "г. Москва, ул. Горького, д. 5, кв. 8",
            "cadastral_number": "77:01:0000000:5",
            "area": 55.0,
            "ownership_type": "Собственность",
            "registration_date": "12.11.2020",
            "passport_series": "45",
            "passport_number": "3333333",
            "inn": "333333333333",
            "snils": "33333333333",
            "phone": "+79003333333",
            "email": "kuznecov.alexey@mail.ru",
            "birth_date": "12.11.1982",
            "birth_place": "г. Екатеринбург"
        },
        {
            "full_name": "Смирнов Дмитрий Васильевич",
            "address": "г. Москва, ул. Садовая, д. 6, кв. 12",
            "cadastral_number": "77:01:0000000:6",
            "area": 42.3,
            "ownership_type": "Собственность",
            "registration_date": "23.12.2020",
            "passport_series": "45",
            "passport_number": "4444444",
            "inn": "444444444444",
            "snils": "44444444444",
            "phone": "+79004444444",
            "email": "smirnov.dmitry@mail.ru",
            "birth_date": "23.12.1979",
            "birth_place": "г. Новосибирск"
        },
        {
            "full_name": "Дуров Павел Валерьевич",
            "address": "г. Москва, ул. Ленинградская, д. 10, кв. 20",
            "cadastral_number": "77:01:0000000:10",
            "area": 120.5,
            "ownership_type": "Собственность",
            "registration_date": "01.01.2020",
            "passport_series": "40",
            "passport_number": "1234567",
            "inn": "123456789012",
            "snils": "12345678901",
            "phone": "+79000000001",
            "email": "durov@telegram.org",
            "birth_date": "10.10.1984",
            "birth_place": "г. Ленинград"
        },
        {
            "full_name": "Морозов Александр Сергеевич",
            "address": "г. Москва, ул. Мира, д. 7, кв. 8",
            "cadastral_number": "77:01:0000000:7",
            "area": 38.7,
            "ownership_type": "Собственность",
            "registration_date": "04.02.2021",
            "passport_series": "45",
            "passport_number": "5555555",
            "inn": "555555555555",
            "snils": "55555555555",
            "phone": "+79005555555",
            "email": "morozov.alexander@mail.ru",
            "birth_date": "04.02.1987",
            "birth_place": "г. Красноярск"
        },
        {
            "full_name": "Волков Алексей Владимирович",
            "address": "г. Москва, ул. Молодежная, д. 8, кв. 3",
            "cadastral_number": "77:01:0000000:8",
            "area": 50.0,
            "ownership_type": "Собственность",
            "registration_date": "17.03.2021",
            "passport_series": "45",
            "passport_number": "6666666",
            "inn": "666666666666",
            "snils": "66666666666",
            "phone": "+79006666666",
            "email": "volkov.alexey@mail.ru",
            "birth_date": "17.03.1992",
            "birth_place": "г. Казань"
        },
        {
            "full_name": "Соколов Михаил Иванович",
            "address": "г. Москва, ул. Парковая, д. 9, кв. 6",
            "cadastral_number": "77:01:0000000:9",
            "area": 63.8,
            "ownership_type": "Долевая собственность",
            "registration_date": "28.04.2021",
            "passport_series": "45",
            "passport_number": "7777777",
            "inn": "777777777777",
            "snils": "77777777777",
            "phone": "+79007777777",
            "email": "sokolov.mikhail@mail.ru",
            "birth_date": "28.04.1981",
            "birth_place": "г. Санкт-Петербург"
        }
    ]
    
    # Заполняем основную таблицу
    for person in people_data:
        c.execute('''
            INSERT INTO egrn (full_name, address, cadastral_number, area, ownership_type, registration_date,
                             passport_series, passport_number, inn, snils, phone, email, birth_date, birth_place)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            person["full_name"],
            person["address"],
            person["cadastral_number"],
            person["area"],
            person["ownership_type"],
            person["registration_date"],
            person["passport_series"],
            person["passport_number"],
            person["inn"],
            person["snils"],
            person["phone"],
            person["email"],
            person["birth_date"],
            person["birth_place"]
        ))
        
        # Заполняем таблицу паспортов
        c.execute('''
            INSERT INTO passports (full_name, passport_series, passport_number, issued_by, issue_date, birth_date, birth_place)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            person["full_name"],
            person["passport_series"],
            person["passport_number"],
            "УФМС России по г. Москве",
            "15.03.2010",
            person["birth_date"],
            person["birth_place"]
        ))
        
        # Заполняем таблицу телефонов
        c.execute('''
            INSERT INTO phones (full_name, phone, source)
            VALUES (?, ?, ?)
        ''', (
            person["full_name"],
            person["phone"],
            "ЕГРН"
        ))
        
        # Заполняем таблицу ИНН/СНИЛС
        c.execute('''
            INSERT INTO snils_inn (full_name, inn, snils)
            VALUES (?, ?, ?)
        ''', (
            person["full_name"],
            person["inn"],
            person["snils"]
        ))
    
    conn.commit()
    conn.close()
    logging.info("Базы данных успешно созданы")

# Создаём базу при запуске
create_database()

# ===== ПОЛНЫЙ ПОИСК ПО БАЗАМ =====
def search_all_databases(query):
    """Поиск по всем базам данных"""
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
        "source": "База данных"
    }
    
    try:
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "data", "egrn.db"))
        c = conn.cursor()
        
        # Поиск по ФИО
        c.execute('''
            SELECT full_name, address, cadastral_number, area, ownership_type, registration_date,
                   passport_series, passport_number, inn, snils, phone, email, birth_date, birth_place
            FROM egrn
            WHERE full_name LIKE ?
        ''', (f'%{query}%',))
        
        rows = c.fetchall()
        if rows:
            row = rows[0]
            result["full_name"] = row[0]
            result["address"] = row[1]
            result["passport_series"] = row[7]
            result["passport_number"] = row[8]
            result["inn"] = row[9]
            result["snils"] = row[10]
            result["phone"] = row[11]
            result["email"] = row[12]
            result["birth_date"] = row[13]
            result["birth_place"] = row[14]
            result["source"] = "ЕГРН"
        else:
            # Поиск в паспортной базе
            c.execute('''
                SELECT full_name, passport_series, passport_number, issued_by, issue_date, birth_date, birth_place
                FROM passports
                WHERE full_name LIKE ?
            ''', (f'%{query}%',))
            rows = c.fetchall()
            if rows:
                row = rows[0]
                result["full_name"] = row[0]
                result["passport_series"] = row[1]
                result["passport_number"] = row[2]
                result["birth_date"] = row[5]
                result["birth_place"] = row[6]
                result["source"] = "Паспортная база"
            
            # Поиск в телефонной базе
            if not result["full_name"]:
                c.execute('''
                    SELECT full_name, phone
                    FROM phones
                    WHERE full_name LIKE ? OR phone LIKE ?
                ''', (f'%{query}%', f'%{query}%'))
                rows = c.fetchall()
                if rows:
                    result["full_name"] = rows[0][0]
                    result["phone"] = rows[0][1]
                    result["source"] = "Телефонная база"
            
            # Поиск в ИНН/СНИЛС базе
            if not result["full_name"]:
                c.execute('''
                    SELECT full_name, inn, snils
                    FROM snils_inn
                    WHERE full_name LIKE ?
                ''', (f'%{query}%',))
                rows = c.fetchall()
                if rows:
                    result["full_name"] = rows[0][0]
                    result["inn"] = rows[0][1]
                    result["snils"] = rows[0][2]
                    result["source"] = "ИНН/СНИЛС база"
        
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка при поиске в базах: {e}")
    
    return result

# ===== ОСНОВНАЯ ЛОГИКА ПОИСКА =====
async def smart_search(query, user_id):
    if is_banned(user_id):
        return {"personal": {"Ошибка": "❌ Вы были заблокированы администратором."}}

    result = {
        "personal": {},
        "phone": None,
        "email": None,
        "social": [],
        "breaches": 0,
        "source": None
    }

    # --- 1. Поиск в базах данных ---
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
        return result

    # --- 2. Поиск в VK ---
    try:
        vk_api = f"https://api.vk.com/method/users.search?q={query}&count=3&v=5.131"
        r = requests.get(vk_api, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "response" in data and data["response"]["count"] > 0:
                for user in data["response"]["items"]:
                    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    city = user.get("city", {}).get("title", "Неизвестно")
                    result["social"].append(f"✅ VK: https://vk.com/id{user['id']} ({name}, {city})")
                    if not result["personal"].get("ФИО"):
                        result["personal"]["ФИО"] = name
                    if not result["personal"].get("Адрес"):
                        result["personal"]["Адрес"] = city
                    break
    except:
        pass

    # --- 3. Поиск в Telegram ---
    nick = query.replace(" ", "_")
    try:
        tg_url = f"https://t.me/{nick}"
        r = requests.head(tg_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"✅ Telegram: {tg_url}")
    except:
        pass

    # --- 4. Проверка утечек email ---
    if '@' in query:
        email = query.strip()
        result["email"] = email
        try:
            sha1 = hashlib.sha1(email.encode()).hexdigest().upper()
            prefix, suffix = sha1[:5], sha1[5:]
            r = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
            for line in r.text.splitlines():
                if line.startswith(suffix):
                    result["breaches"] = int(line.split(":")[1])
                    break
        except:
            pass

    # --- 5. Если ничего не найдено ---
    if not result["personal"] and not result["social"]:
        result["personal"]["Информация"] = "❌ Ничего не найдено. Попробуйте уточнить запрос."

    return result

def generate_html_report(query, user_id, username, data):
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
        for k, v in data["personal"].items():
            html += f'    <div class="item">{k}: {v}</div>\n'
    if data.get("phone"):
        html += f'    <div class="item">📱 Телефон: {data["phone"]}</div>\n'
    if data.get("email"):
        html += f'    <div class="item">📧 Email: {data["email"]}</div>\n'
    if data.get("breaches") and data["breaches"] > 0:
        html += f'    <div class="item">🔴 Утечки: {data["breaches"]}</div>\n'

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

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
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

# ===== КОМАНДА /start =====
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
        f"🔍 Введите ФИО, номер телефона, ник Telegram, IP или Email.\n"
        f"📌 Бот ищет по локальным базам ЕГРН, паспортным данным, ИНН, СНИЛС, телефонам.\n"
        f"📡 Источники: ЕГРН, паспортная база, телефонная база, ИНН/СНИЛС база, VK, Telegram.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ===== КОЛБЭКИ МЕНЮ =====
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

# ===== АДМИН-КОМАНДЫ =====
def is_admin(user_id):
    return user_id in ADMIN_IDS

async def give_queries(update, context):
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

async def steal_queries(update, context):
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

async def delete_check(update, context):
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

async def block_user(update, context):
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

async def block_ip(update, context):
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

async def unblock_user(update, context):
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

async def unblock_ip(update, context):
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

async def banlist(update, context):
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

async def iplist(update, context):
    if not is_admin(update.effective_user.id):
        return
    if not banned_ips:
        await update.message.reply_text("📊 Список заблокированных IP пуст")
        return
    msg = "📊 *Заблокированные IP:*\n"
    for ip in banned_ips:
        msg += f"• {ip}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_limit(update, context):
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

async def broadcast(update, context):
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

async def create_check(update, context):
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

async def activate_check(update, context):
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

# ===== ЗАПУСК =====
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
