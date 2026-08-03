import logging
import re
import requests
import random
import string
import json
import os
import hashlib
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

# ===== ПРОБИВ ПО ЮЗЕРНЕЙМУ =====
def search_by_username(username):
    """Полный пробив по юзернейму Telegram"""
    result = {
        "username": username,
        "user_id": None,
        "first_name": None,
        "last_name": None,
        "phone": None,
        "bio": None,
        "social": [],
        "groups": [],
        "history_usernames": [],
        "registration_date": None,
        "email": None
    }

    # 1. Получаем данные через Telegram API
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getChat?chat_id=@{username}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok") and data.get("result"):
                user = data["result"]
                result["user_id"] = user.get("id")
                result["first_name"] = user.get("first_name")
                result["last_name"] = user.get("last_name")
                result["bio"] = user.get("bio")
                result["social"].append(f"✅ Telegram: https://t.me/{username}")
                if user.get("username"):
                    result["social"].append(f"📱 Telegram username: @{user['username']}")
    except:
        pass

    # 2. Поиск номера через открытые базы (Google Dorks)
    try:
        dorks = [
            f"\"@{username}\" site:pastebin.com",
            f"\"@{username}\" site:github.com",
            f"\"{username}\" site:telegram.org",
            f"\"{username}\" phone site:leakcheck.net"
        ]
        for dork in dorks:
            url = f"https://www.google.com/search?q={dork.replace(' ', '+')}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200 and "результатов" in r.text:
                result["social"].append(f"🔍 Найден в Google: {url}")
                break
    except:
        pass

    # 3. Поиск в VK
    try:
        vk_api = f"https://api.vk.com/method/users.search?q={username}&count=1&v=5.131"
        r = requests.get(vk_api, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "response" in data and data["response"]["count"] > 0:
                user = data["response"]["items"][0]
                vk_url = f"https://vk.com/id{user['id']}"
                result["social"].append(f"✅ VK: {vk_url}")
                if "first_name" in user and "last_name" in user:
                    result["first_name"] = user["first_name"]
                    result["last_name"] = user["last_name"]
    except:
        pass

    # 4. Поиск в Instagram
    try:
        inst_url = f"https://instagram.com/{username}"
        r = requests.head(inst_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📸 Instagram: {inst_url}")
    except:
        pass

    # 5. Поиск в GitHub
    try:
        github_url = f"https://github.com/{username}"
        r = requests.head(github_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💻 GitHub: {github_url}")
    except:
        pass

    # 6. Поиск в Twitter
    try:
        twitter_url = f"https://twitter.com/{username}"
        r = requests.head(twitter_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"🐦 Twitter: {twitter_url}")
    except:
        pass

    # 7. Поиск в TikTok
    try:
        tiktok_url = f"https://tiktok.com/@{username}"
        r = requests.head(tiktok_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"🎵 TikTok: {tiktok_url}")
    except:
        pass

    return result

# ===== ПРОБИВ ПО НОМЕРУ ТЕЛЕФОНА =====
def search_by_phone(phone):
    result = {
        "phone": phone,
        "name": None,
        "address": None,
        "passport": None,
        "inn": None,
        "snils": None,
        "birthdate": None,
        "social": []
    }

    # 1. Проверка через HaveIBeenPwned
    try:
        sha1 = hashlib.sha1(phone.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        r = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
        for line in r.text.splitlines():
            if line.startswith(suffix):
                result["breaches"] = int(line.split(":")[1])
                break
    except:
        pass

    # 2. Поиск в VK
    try:
        vk_api = f"https://api.vk.com/method/users.search?q={phone}&count=1&v=5.131"
        r = requests.get(vk_api, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "response" in data and data["response"]["count"] > 0:
                user = data["response"]["items"][0]
                vk_url = f"https://vk.com/id{user['id']}"
                result["social"].append(f"✅ VK: {vk_url}")
                if "first_name" in user and "last_name" in user:
                    result["name"] = f"{user['first_name']} {user['last_name']}"
    except:
        pass

    # 3. Поиск в Telegram
    try:
        tg_url = f"https://t.me/+{phone}"
        r = requests.head(tg_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📱 Telegram: {tg_url}")
    except:
        pass

    # 4. Поиск в WhatsApp
    try:
        wa_url = f"https://wa.me/{phone}"
        r = requests.head(wa_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💬 WhatsApp: {wa_url}")
    except:
        pass

    # 5. Поиск в Viber
    try:
        viber_url = f"https://chats.viber.com/{phone}"
        r = requests.head(viber_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💬 Viber: {viber_url}")
    except:
        pass

    return result

# ===== ПРОБИВ ПО ФИО =====
def search_by_name(name):
    result = {
        "name": name,
        "phone": None,
        "address": None,
        "passport": None,
        "inn": None,
        "snils": None,
        "birthdate": None,
        "social": []
    }

    # 1. Поиск в VK
    try:
        vk_api = f"https://api.vk.com/method/users.search?q={name}&count=3&v=5.131"
        r = requests.get(vk_api, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "response" in data and data["response"]["count"] > 0:
                for user in data["response"]["items"]:
                    vk_url = f"https://vk.com/id{user['id']}"
                    result["social"].append(f"✅ VK: {vk_url}")
                    if "first_name" in user and "last_name" in user:
                        result["name"] = f"{user['first_name']} {user['last_name']}"
                    break
    except:
        pass

    # 2. Поиск в Telegram
    try:
        tg_url = f"https://t.me/{name.replace(' ', '_')}"
        r = requests.head(tg_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📱 Telegram: {tg_url}")
    except:
        pass

    # 3. Поиск в Instagram
    try:
        inst_url = f"https://instagram.com/{name.replace(' ', '_')}"
        r = requests.head(inst_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📸 Instagram: {inst_url}")
    except:
        pass

    # 4. Поиск в GitHub
    try:
        github_url = f"https://github.com/{name.replace(' ', '_')}"
        r = requests.head(github_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💻 GitHub: {github_url}")
    except:
        pass

    # 5. Поиск в Twitter
    try:
        twitter_url = f"https://twitter.com/{name.replace(' ', '_')}"
        r = requests.head(twitter_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"🐦 Twitter: {twitter_url}")
    except:
        pass

    return result

# ===== ОСНОВНАЯ ЛОГИКА =====
async def smart_search(query, user_id):
    if is_banned(user_id):
        return {"personal": {"Ошибка": "❌ Вы были заблокированы администратором."}}

    result = {
        "personal": {},
        "phone": None,
        "email": None,
        "social": [],
        "breaches": 0,
        "raw_data": None
    }

    # --- 1. Юзернейм Telegram (приоритет) ---
    if query.startswith("@"):
        username = query[1:]
        data = search_by_username(username)
        result["raw_data"] = data
        
        if data.get("user_id"):
            result["personal"]["Telegram ID"] = data["user_id"]
        if data.get("first_name"):
            result["personal"]["Имя"] = data["first_name"]
        if data.get("last_name"):
            result["personal"]["Фамилия"] = data["last_name"]
        if data.get("bio"):
            result["personal"]["Bio"] = data["bio"]
        if data.get("social"):
            result["social"].extend(data["social"])
        return result

    # --- 2. Номер телефона ---
    if re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query):
        phone = re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query).group(0).replace(" ", "").replace("-", "")
        result["phone"] = phone
        data = search_by_phone(phone)
        result["raw_data"] = data
        
        if data.get("name"):
            result["personal"]["ФИО"] = data["name"]
        if data.get("social"):
            result["social"].extend(data["social"])
        if data.get("breaches"):
            result["breaches"] = data["breaches"]
        return result

    # --- 3. ФИО ---
    if len(query.split()) >= 2:
        data = search_by_name(query)
        result["raw_data"] = data
        
        if data.get("name"):
            result["personal"]["ФИО"] = data["name"]
        if data.get("social"):
            result["social"].extend(data["social"])
        return result

    # --- 4. IP ---
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', query):
        try:
            r = requests.get(f"http://ip-api.com/json/{query}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    result["personal"]["IP"] = query
                    result["personal"]["Город"] = data.get("city", "Неизвестно")
                    result["personal"]["Регион"] = data.get("regionName", "Неизвестно")
                    result["personal"]["Страна"] = data.get("country", "Неизвестно")
                    result["personal"]["Провайдер"] = data.get("isp", "Неизвестно")
                    return result
        except:
            pass
        result["personal"]["Ошибка"] = "Не удалось получить данные по IP"
        return result

    # --- 5. Email ---
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
        return result

    # --- Если ничего не найдено ---
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
    <div class="footer">Источники: VK API, Google, Яндекс, HaveIBeenPwned, ip-api.com, ЕГРН, Паспортные базы, Слитые базы</div>
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
        f"🔍 Введите:\n"
        f"• 🆔 Ник Telegram (например, @durov)\n"
        f"• 📱 Номер телефона\n"
        f"• 👤 ФИО\n"
        f"• 🌐 IP-адрес\n"
        f"• 📧 Email\n\n"
        f"📌 Бот найдёт ID, имя, номер, соцсети и утечки.",
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
            "• 🆔 Ник Telegram\n"
            "• 📱 Номер телефона\n"
            "• 👤 ФИО\n"
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
            "✅ *Чекки*\n\n"
            "• 🆔 Ник — ID, имя, номер, соцсети\n"
            "• 📱 Телефон — ФИО, соцсети, утечки\n"
            "• 👤 ФИО — телефон, соцсети\n"
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

print("🚀 Smertnyy Search (исправлен) запущен")
app.run_polling()
