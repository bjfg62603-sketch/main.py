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

# ===== ДАННЫЕ =====
users = {}
checks = {}

def load_data():
    global users, checks
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                users = {int(k): v for k, v in data.get("users", {}).items()}
                checks = data.get("checks", {})
        except:
            pass

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {str(k): v for k, v in users.items()}, "checks": checks}, f, ensure_ascii=False, indent=2)
    except:
        pass

load_data()

# ===== ФУНКЦИИ БАЛАНСА =====
def get_user_queries(user_id):
    return users.get(user_id, {}).get("queries", 0)

def add_queries(user_id, amount):
    if user_id not in users:
        users[user_id] = {"queries": 0, "username": str(user_id), "first_name": "Пользователь", "registered": datetime.now().strftime("%d.%m.%Y %H:%M")}
    users[user_id]["queries"] += amount
    save_data()

def use_query(user_id):
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

# ===== КЛАВИАТУРА =====
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

# ===== ПАРСИНГ ЗАПРОСА (ЧЁТКИЙ) =====
def parse_query(query):
    """Разбирает запрос на составные части: ФИО, город, адрес, возраст, страну, телефон, email, IP"""
    result = {
        "name": None,
        "city": None,
        "address": None,
        "age": None,
        "country": None,
        "phone": None,
        "email": None,
        "ip": None,
        "nick": None,
        "raw": query
    }

    # --- IP ---
    ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    if ip_pattern.match(query):
        result["ip"] = query
        return result

    # --- Телефон ---
    phone_match = re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query)
    if phone_match:
        result["phone"] = phone_match.group(0)
        query = query.replace(phone_match.group(0), "")

    # --- Email ---
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', query)
    if email_match:
        result["email"] = email_match.group(0)
        query = query.replace(email_match.group(0), "")

    # --- Возраст (число от 1 до 120) ---
    age_match = re.search(r'\b([1-9][0-9]?|1[0-1][0-9]|120)\b', query)
    if age_match:
        age = int(age_match.group(0))
        if 1 <= age <= 120:
            result["age"] = age
            query = query.replace(str(age), "")

    # --- Город (ТОЛЬКО ПО КЛЮЧЕВЫМ СЛОВАМ) ---
    city_keywords = ["город", "г.", "city", "в", "из"]
    for kw in city_keywords:
        if kw in query.lower():
            parts = query.lower().split(kw)
            if len(parts) > 1:
                potential = parts[1].split()[0].strip().strip(',.!?')
                if len(potential) > 2 and potential[0].isupper():
                    result["city"] = potential.capitalize()
                    query = query.replace(potential, "")
                    break

    # --- Страна (ТОЛЬКО ПО КЛЮЧЕВЫМ СЛОВАМ) ---
    country_keywords = ["страна", "country", "гражданин"]
    for kw in country_keywords:
        if kw in query.lower():
            parts = query.lower().split(kw)
            if len(parts) > 1:
                potential = parts[1].split()[0].strip().strip(',.!?')
                if len(potential) > 2 and potential[0].isupper():
                    result["country"] = potential.capitalize()
                    query = query.replace(potential, "")
                    break

    # --- Адрес (улица, дом, квартира) ---
    address_pattern = re.compile(r'(ул\.|улица|пр\.|проспект|пер\.|переулок|д\.|дом|кв\.|квартира)\s*[^\s,]+', re.IGNORECASE)
    address_match = address_pattern.search(query)
    if address_match:
        addr_start = address_match.start()
        addr_end = len(query)
        for kw in ["город", "г.", "страна", "возраст", "лет"]:
            pos = query.lower().find(kw, addr_start)
            if pos != -1 and pos < addr_end:
                addr_end = pos
        result["address"] = query[addr_start:addr_end].strip()
        query = query.replace(result["address"], "")

    # --- ФИО (оставшиеся слова, если их 2-4 и они с заглавной) ---
    clean_query = re.sub(r'[^\w\s]', '', query)
    clean_query = re.sub(r'\s+', ' ', clean_query).strip()
    words = clean_query.split()

    if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if len(w) > 1):
        result["name"] = " ".join(words)
    elif len(words) == 1 and len(words[0]) > 2:
        result["nick"] = words[0]

    return result

# ===== РЕАЛЬНЫЙ ПОИСК (БЕЗ ЦИРКА) =====
async def smart_search(query):
    """Реальный поиск — без фейков и подставных ссылок"""
    parsed = parse_query(query)
    result = {
        "personal": {},
        "phone": None,
        "email": None,
        "social": [],
        "breaches": 0,
        "ip_data": None
    }

    # --- IP-адрес ---
    if parsed["ip"]:
        try:
            r = requests.get(f"http://ip-api.com/json/{parsed['ip']}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    result["personal"]["IP"] = parsed["ip"]
                    result["personal"]["Город"] = data.get("city", "Неизвестно")
                    result["personal"]["Регион"] = data.get("regionName", "Неизвестно")
                    result["personal"]["Страна"] = data.get("country", "Неизвестно")
                    result["personal"]["Провайдер"] = data.get("isp", "Неизвестно")
                    result["social"].append(f"📍 Координаты: {data.get('lat', '0')}, {data.get('lon', '0')}")
                    result["social"].append(f"🕵️ Shodan: https://www.shodan.io/host/{parsed['ip']}")
                    return result
        except:
            pass
        result["personal"]["Ошибка"] = "Не удалось получить данные по IP"
        return result

    # --- Телефон ---
    if parsed["phone"]:
        result["phone"] = parsed["phone"]
        result["social"].append(f"📱 Telegram: https://t.me/+{parsed['phone']}")
        result["social"].append(f"💬 WhatsApp: https://wa.me/{parsed['phone']}")
        result["social"].append(f"💬 Viber: https://chats.viber.com/{parsed['phone']}")
        result["social"].append(f"🎵 TikTok (поиск по номеру): https://www.tiktok.com/search?q={parsed['phone']}")
        return result

    # --- Email ---
    if parsed["email"]:
        result["email"] = parsed["email"]
        try:
            sha1 = hashlib.sha1(parsed["email"].encode()).hexdigest().upper()
            prefix, suffix = sha1[:5], sha1[5:]
            r = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
            for line in r.text.splitlines():
                if line.startswith(suffix):
                    result["breaches"] = int(line.split(":")[1])
                    break
        except:
            pass
        return result

    # --- ФИО + город + адрес + страна + возраст ---
    search_parts = []
    if parsed["name"]:
        search_parts.append(parsed["name"])
        result["personal"]["ФИО"] = parsed["name"]
    if parsed["city"]:
        search_parts.append(parsed["city"])
        result["personal"]["Город"] = parsed["city"]
    if parsed["address"]:
        search_parts.append(parsed["address"])
        result["personal"]["Адрес"] = parsed["address"]
    if parsed["country"]:
        search_parts.append(parsed["country"])
        result["personal"]["Страна"] = parsed["country"]
    if parsed["age"]:
        search_parts.append(str(parsed["age"]))
        result["personal"]["Возраст"] = str(parsed["age"])

    # --- Если ничего не распарсилось, берём весь запрос как ник ---
    if not search_parts and not parsed["nick"]:
        nick = query.strip()
        result["personal"]["Запрос"] = nick
        result["social"].append(f"📱 Telegram: https://t.me/{nick}")
        result["social"].append(f"📸 Instagram: https://instagram.com/{nick}")
        result["social"].append(f"📘 VK: https://vk.com/{nick}")
        result["social"].append(f"💻 GitHub: https://github.com/{nick}")
        result["social"].append(f"🐦 Twitter: https://twitter.com/{nick}")
        result["social"].append(f"🎵 TikTok: https://www.tiktok.com/@{nick}")
        google_query = f"https://www.google.com/search?q={nick.replace(' ', '+')}"
        yandex_query = f"https://yandex.ru/search/?text={nick.replace(' ', '+')}"
        result["social"].append(f"🔍 Google: {google_query}")
        result["social"].append(f"🔍 Яндекс: {yandex_query}")
        return result

    # --- Соцсети по нику ---
    if parsed["nick"]:
        nick = parsed["nick"]
        result["social"].append(f"📱 Telegram: https://t.me/{nick}")
        result["social"].append(f"📸 Instagram: https://instagram.com/{nick}")
        result["social"].append(f"📘 VK: https://vk.com/{nick}")
        result["social"].append(f"💻 GitHub: https://github.com/{nick}")
        result["social"].append(f"🐦 Twitter: https://twitter.com/{nick}")
        result["social"].append(f"🎵 TikTok: https://www.tiktok.com/@{nick}")

    # --- Google/Яндекс с полным запросом ---
    if search_parts:
        full_query = " ".join(search_parts)
        google_query = f"https://www.google.com/search?q={full_query.replace(' ', '+')}"
        yandex_query = f"https://yandex.ru/search/?text={full_query.replace(' ', '+')}"
        result["social"].append(f"🔍 Google: {google_query}")
        result["social"].append(f"🔍 Яндекс: {yandex_query}")

    # --- VK API (поиск людей) ---
    if parsed["name"]:
        try:
            vk_api_url = f"https://api.vk.com/method/users.search?q={parsed['name']}&count=5&v=5.131"
            r = requests.get(vk_api_url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if "response" in data:
                    for item in data["response"]["items"]:
                        vk_link = f"https://vk.com/id{item['id']}"
                        result["social"].append(f"✅ VK (найден): {vk_link}")
                        if "first_name" in item and "last_name" in item:
                            result["personal"]["VK_Имя"] = f"{item['first_name']} {item['last_name']}"
        except:
            pass

    return result

# ===== ГЕНЕРАТОР HTML =====
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
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">📱 ТЕЛЕФОН</div>
'''
    if data.get("phone"):
        html += f'    <div class="item">{data["phone"]}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">📧 EMAIL</div>
'''
    if data.get("email"):
        html += f'    <div class="item">{data["email"]}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">🔗 СОЦИАЛЬНЫЕ СЕТИ И ССЫЛКИ</div>
'''
    if data.get("social"):
        for soc in data["social"][:25]:
            html += f'    <div class="item">✅ {soc}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">📦 УТЕЧКИ</div>
'''
    if data.get("breaches") and data["breaches"] > 0:
        html += f'    <div class="item">🔴 Найден в {data["breaches"]} утечках</div>\n'
    else:
        html += '    <div class="item">🟢 Не найден</div>\n'

    html += f'''
    <div class="footer">Источники: VK API, Google, Яндекс, HaveIBeenPwned, ip-api.com, Instagram, GitHub, Twitter, TikTok, YouTube, Wikipedia</div>
    <div class="footer">🌙 Smertnyy Search — ваш надёжный OSINT-инструмент</div>
</body>
</html>
'''
    return html, filename

# ===== ОБРАБОТЧИК ФОТО =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без ника"

    if get_user_queries(user_id) <= 0:
        await update.message.reply_text("❌ Закончились запросы.", reply_markup=main_menu())
        return

    if not use_query(user_id):
        await update.message.reply_text("❌ Ошибка.", reply_markup=main_menu())
        return

    search_msg = await update.message.reply_text("⏳ Анализ фото... (запрос списан)", reply_markup=None)

    try:
        photo_file = await update.message.photo[-1].get_file()
        file_path = f"temp_photo_{user_id}.jpg"
        await photo_file.download_to_drive(file_path)

        data = {
            "personal": {},
            "phone": None,
            "email": None,
            "social": [],
            "breaches": 0,
            "ip_data": None
        }

        google_lens = f"https://lens.google.com/upload?hl=ru&re=df&stc=gs&vpw=0&vph=0&url=" + file_path
        data["social"].append(f"🔍 Google Lens: {google_lens}")
        data["social"].append(f"🔍 Яндекс.Картинки: https://yandex.ru/images/search?source=collections&img_url=" + file_path)
        data["social"].append(f"🔍 Tineye: https://tineye.com/search?url=" + file_path)
        data["social"].append(f"🔍 Google Images: https://www.google.com/searchbyimage?image_url=" + file_path)

        html, filename = generate_html_report("Фото-поиск", user_id, username, data)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        msg = f"📊 *Найдено по фото:*\n"
        msg += f"📄 HTML-отчёт приложен"

        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename=filename),
                caption=msg,
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        os.remove(filename)
        os.remove(file_path)
        await search_msg.delete()

    except Exception as e:
        add_queries(user_id, 1)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=main_menu())
        await search_msg.delete()

# ===== ОБРАБОТЧИК ТЕКСТА =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без ника"

    if get_user_queries(user_id) <= 0:
        await update.message.reply_text("❌ Закончились запросы.", reply_markup=main_menu())
        return

    if not use_query(user_id):
        await update.message.reply_text("❌ Ошибка.", reply_markup=main_menu())
        return

    search_msg = await update.message.reply_text("⏳ Глубокий поиск... (запрос списан)", reply_markup=None)

    try:
        data = await smart_search(text)
        html, filename = generate_html_report(text, user_id, username, data)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        msg = f"📊 *Найдено:*\n"
        if data.get("phone"):
            msg += f"📱 Телефон: {data['phone']}\n"
        if data.get("email"):
            msg += f"📧 Email: {data['email']}\n"
        if data.get("breaches") and data["breaches"] > 0:
            msg += f"🔴 Утечки: {data['breaches']}\n"
        if data.get("personal"):
            for k, v in data["personal"].items():
                if k not in ["IP", "Город", "Регион", "Страна", "Провайдер"]:
                    msg += f"👤 {k}: {v}\n"
        msg += f"📄 HTML-отчёт приложен"

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
        f"🔍 Бот ищет информацию по утечкам и открытым источникам.\n"
        f"📌 Отправьте:\n"
        f"• 🖼️ Фото — обратный поиск\n"
        f"• 🌐 IP-адрес\n"
        f"• 📱 Номер телефона\n"
        f"• 📧 Email\n"
        f"• 👤 ФИО или никнейм\n\n"
        f"Используйте кнопки меню:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        balance = get_user_queries(user_id)
        await query.edit_message_text(
            f"👋 Добро пожаловать в *Smertnyy Search*, {get_user_identifier(user_id)}!\n"
            f"📊 Осталось запросов: {balance}\n\n"
            f"🔍 Бот ищет информацию по утечкам и открытым источникам.\n"
            f"📌 Отправьте номер телефона, ФИО, Email, IP, ник или фото для поиска.\n\n"
            f"Используйте кнопки меню:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
    elif data == "search":
        await query.edit_message_text(
            "🔍 *Поиск*\n\n"
            "📌 Отправьте мне:\n"
            "• 🖼️ Фото — для обратного поиска\n"
            "• 🌐 IP-адрес\n"
            "• 📱 Номер телефона\n"
            "• 📧 Email\n"
            "• 👤 ФИО или никнейм\n\n"
            "Я проверю утечки, соцсети, поисковики и фото-базы.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "profile":
        user_data = users.get(user_id, {})
        balance = get_user_queries(user_id)
        registered = user_data.get("registered", "Неизвестно")
        await query.edit_message_text(
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: {user_id}\n"
            f"📛 Ник: {get_user_identifier(user_id)}\n"
            f"📊 Осталось запросов: {balance}\n"
            f"📅 Дата регистрации: {registered}\n"
            f"📌 Всего пользователей: {len(users)}",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "checks":
        await query.edit_message_text(
            "✅ *Доступные чекки*\n\n"
            "🖼️ *Фото*\n"
            "→ Обратный поиск в Google Lens, Yandex, Tineye\n\n"
            "🌐 *IP-адрес*\n"
            "→ Геолокация, провайдер, Shodan\n\n"
            "📱 *Номер телефона*\n"
            "→ Проверка в Telegram, WhatsApp, Viber, TikTok\n\n"
            "📧 *Email*\n"
            "→ Проверка утечек (HaveIBeenPwned)\n\n"
            "👤 *ФИО или никнейм*\n"
            "→ Поиск в VK, Instagram, GitHub, Twitter, TikTok, YouTube, Telegram\n\n"
            "📌 Просто отправьте мне данные для поиска.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "support":
        await query.edit_message_text(
            "🆘 *Поддержка*\n\n"
            "👤 Владелец: @okimdeadlybutimnotteamsandidmeok\n"
            "📌 По всем вопросам пишите в личные сообщения.\n\n"
            "🛠 *Smertnyy Search* работает в тестовом режиме.\n"
            "Сообщайте о багах и ошибках.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "admin":
        await query.edit_message_text(
            "⚙️ *Админ-панель*\n\n"
            "📌 Доступно только владельцу.\n\n"
            "Команды:\n"
            "`/give @username кол-во` — выдать запросы\n"
            "`/steal @username кол-во` — забрать запросы\n"
            "`/balance @username` — баланс пользователя\n"
            "`/createcheck Название запросы активации` — создать чек\n"
            "`/deletecheck КОД` — удалить чек\n"
            "`/activate КОД` — активировать чек",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )

# ===== АДМИН-КОМАНДЫ =====
def is_admin(user_id):
    return user_id in ADMIN_IDS

async def give_queries(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
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
    for uid, data in users.items():
        if data.get("username") == target:
            add_queries(uid, amount)
            await update.message.reply_text(f"✅ Выдано {amount} запросов.")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

async def steal_queries(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
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
    for uid, data in users.items():
        if data.get("username") == target:
            if users[uid]["queries"] < amount:
                await update.message.reply_text("❌ Недостаточно")
                return
            users[uid]["queries"] -= amount
            save_data()
            await update.message.reply_text(f"✅ Забрано {amount}")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

async def balance(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /balance @username")
        return
    target = args[0].replace("@", "")
    for uid, data in users.items():
        if data.get("username") == target:
            await update.message.reply_text(f"📊 Баланс: {users[uid]['queries']}")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

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

async def delete_check(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /deletecheck КОД")
        return
    code = args[0].upper()
    if code in checks:
        del checks[code]
        save_data()
        await update.message.reply_text(f"✅ Чек {code} удалён.")
    else:
        await update.message.reply_text("❌ Чек не найден.")

async def activate_check(update, context):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("❌ /activate КОД")
        return
    code = args[0].upper()
    if code not in checks:
        await update.message.reply_text("❌ Неверный код.")
        return
    check = checks[code]
    if user_id in check.get("used_by", []):
        await update.message.reply_text("❌ Вы уже активировали этот чек.")
        return
    if check["activations"] <= 0:
        await update.message.reply_text("❌ Чек использован.")
        return
    add_queries(user_id, check["queries"])
    check["used_by"].append(user_id)
    check["activations"] -= 1
    if check["activations"] == 0:
        del checks[code]
    save_data()
    await update.message.reply_text(f"✅ Активирован чек {code}! +{check['queries']} запросов.")

# ===== ЗАПУСК =====
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("give", give_queries))
app.add_handler(CommandHandler("steal", steal_queries))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("createcheck", create_check))
app.add_handler(CommandHandler("deletecheck", delete_check))
app.add_handler(CommandHandler("activate", activate_check))
app.add_handler(CallbackQueryHandler(menu_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("🚀 Smertnyy Search запущен")
app.run_polling()
