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

# ===== ПРОБИВ ПО НОМЕРУ ТЕЛЕФОНА =====
def search_by_phone(phone):
    """Ищет информацию по номеру телефона в открытых и теневых источниках"""
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

    # 1. Проверка через HaveIBeenPwned (утечки)
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

    # 2. Поиск в открытых базах (Google Dorks)
    try:
        dorks = [
            f"\"{phone}\" site:pastebin.com",
            f"\"{phone}\" site:github.com",
            f"\"{phone}\" site:telegra.ph",
            f"\"{phone}\" site:instagram.com",
            f"\"{phone}\" site:telegram.org"
        ]
        for dork in dorks:
            url = f"https://www.google.com/search?q={dork.replace(' ', '+')}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200 and "результатов" in r.text:
                result["social"].append(f"🔍 Найден в Google: {url}")
                break
    except:
        pass

    # 3. Проверка в Telegram
    try:
        tg_url = f"https://t.me/+{phone}"
        r = requests.head(tg_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📱 Telegram: {tg_url}")
    except:
        pass

    # 4. Проверка в WhatsApp
    try:
        wa_url = f"https://wa.me/{phone}"
        r = requests.head(wa_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💬 WhatsApp: {wa_url}")
    except:
        pass

    # 5. Проверка в Viber
    try:
        viber_url = f"https://chats.viber.com/{phone}"
        r = requests.head(viber_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💬 Viber: {viber_url}")
    except:
        pass

    # 6. Поиск в VK
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
                if "city" in user and "title" in user["city"]:
                    result["address"] = user["city"]["title"]
    except:
        pass

    # 7. Поиск в Instagram
    try:
        inst_url = f"https://instagram.com/{phone}"
        r = requests.head(inst_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📸 Instagram: {inst_url}")
    except:
        pass

    return result

# ===== ПРОБИВ ПО ФИО =====
def search_by_name(name):
    """Ищет информацию по ФИО в открытых и теневых источниках"""
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
                    if "city" in user and "title" in user["city"]:
                        result["address"] = user["city"]["title"]
                    break
    except:
        pass

    # 2. Поиск в Google
    try:
        google_url = f"https://www.google.com/search?q={name.replace(' ', '+')}"
        r = requests.get(google_url, timeout=5)
        if r.status_code == 200:
            result["social"].append(f"🔍 Google: {google_url}")
    except:
        pass

    # 3. Поиск в Яндекс
    try:
        yandex_url = f"https://yandex.ru/search/?text={name.replace(' ', '+')}"
        r = requests.get(yandex_url, timeout=5)
        if r.status_code == 200:
            result["social"].append(f"🔍 Яндекс: {yandex_url}")
    except:
        pass

    # 4. Поиск в Instagram
    try:
        inst_url = f"https://instagram.com/{name.replace(' ', '_')}"
        r = requests.head(inst_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📸 Instagram: {inst_url}")
    except:
        pass

    # 5. Поиск в Telegram
    try:
        tg_url = f"https://t.me/{name.replace(' ', '_')}"
        r = requests.head(tg_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"📱 Telegram: {tg_url}")
    except:
        pass

    # 6. Поиск в GitHub
    try:
        github_url = f"https://github.com/{name.replace(' ', '_')}"
        r = requests.head(github_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"💻 GitHub: {github_url}")
    except:
        pass

    # 7. Поиск в Twitter
    try:
        twitter_url = f"https://twitter.com/{name.replace(' ', '_')}"
        r = requests.head(twitter_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"🐦 Twitter: {twitter_url}")
    except:
        pass

    # 8. Поиск в TikTok
    try:
        tiktok_url = f"https://tiktok.com/@{name.replace(' ', '_')}"
        r = requests.head(tiktok_url, timeout=3)
        if r.status_code == 200:
            result["social"].append(f"🎵 TikTok: {tiktok_url}")
    except:
        pass

    return result

# ===== ПРОБИВ ПО НИКУ TELEGRAM =====
def search_by_telegram_username(username):
    """Ищет информацию по нику Telegram"""
    result = {
        "username": username,
        "phone": None,
        "user_id": None,
        "first_name": None,
        "last_name": None,
        "social": []
    }

    # 1. Получаем ID пользователя
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
                result["social"].append(f"📱 Telegram: https://t.me/{username}")
    except:
        pass

    # 2. Поиск номера через открытые базы
    try:
        dorks = [
            f"\"@{username}\" site:pastebin.com",
            f"\"@{username}\" site:github.com",
            f"\"{username}\" site:telegram.org"
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
        "source": None,
        "raw_data": None
    }

    # --- Если это номер телефона ---
    if re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query):
        phone = re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query).group(0).replace(" ", "").replace("-", "")
        result["phone"] = phone
        phone_data = search_by_phone(phone)
        if phone_data:
            result["raw_data"] = phone_data
            if phone_data.get("name"):
                result["personal"]["ФИО"] = phone_data["name"]
            if phone_data.get("address"):
                result["personal"]["Адрес"] = phone_data["address"]
            if phone_data.get("birthdate"):
                result["personal"]["Дата рождения"] = phone_data["birthdate"]
            if phone_data.get("social"):
                result["social"].extend(phone_data["social"])
            if phone_data.get("breaches"):
                result["breaches"] = phone_data["breaches"]
        return result

    # --- Если это ФИО ---
    if len(query.split()) >= 2:
        name_data = search_by_name(query)
        if name_data:
            result["raw_data"] = name_data
            if name_data.get("phone"):
                result["phone"] = name_data["phone"]
            if name_data.get("address"):
                result["personal"]["Адрес"] = name_data["address"]
            if name_data.get("social"):
                result["social"].extend(name_data["social"])
        return result

    # --- Если это ник Telegram ---
    if query.startswith("@"):
        username = query[1:]
        tg_data = search_by_telegram_username(username)
        if tg_data:
            result["raw_data"] = tg_data
            if tg_data.get("user_id"):
                result["personal"]["Telegram ID"] = tg_data["user_id"]
            if tg_data.get("first_name"):
                result["personal"]["Имя"] = tg_data["first_name"]
            if tg_data.get("last_name"):
                result["personal"]["Фамилия"] = tg_data["last_name"]
            if tg_data.get("social"):
                result["social"].extend(tg_data["social"])
        return result

    # --- Если это IP ---
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

    # --- Если это Email ---
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
    <div class="category">📌 ИНФОРМАЦИЯ</div>
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
    <div class="footer">Источники: VK API, Google, Яндекс, HaveIBeenPwned, ip-api.com, Telegram API, Слитые базы</div>
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

# ===== КОМАНДЫ =====
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
        f"• 📱 Номер телефона\n"
        f"• 👤 ФИО\n"
        f"• 🆔 Ник Telegram (например, @durov)\n"
        f"• 🌐 IP-адрес\n"
        f"• 📧 Email\n\n"
        f"📌 Бот найдёт ФИО, адрес, паспорт, ИНН, СНИЛС и соцсети.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ===== ОСТАЛЬНЫЕ КОМАНДЫ (АДМИНКА, МЕНЮ, БАНЫ) =====
# ... (все остальные функции из предыдущей версии остаются без изменений)

# ===== ЗАПУСК =====
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
# ... (регистрация всех остальных команд)

print("🚀 Smertnyy Search (режим Безлимит) запущен")
app.run_polling()
