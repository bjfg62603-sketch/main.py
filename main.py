import logging
import re
import requests
import random
import string
import json
import os
import hashlib
import sqlite3
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# ===== КОНФИГ =====
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_IDS = [8428048355]
DATA_FILE = "data.json"
DEFAULT_QUERIES = 5

logging.basicConfig(level=logging.INFO)

# ===== ДАННЫЕ OSINT =====
users = {}
checks = {}
banned_users = set()
banned_ips = set()
user_ips = {}

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

# ===== БАЗА ДАННЫХ ДЛЯ МУТА =====
class MuteDB:
    def __init__(self, db_file="mutes.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS mutes (
                user_id INTEGER,
                chat_id INTEGER,
                muted_until INTEGER,
                PRIMARY KEY (user_id, chat_id)
            )
        """)
        self.conn.commit()
    
    def add_mute(self, user_id: int, chat_id: int, until: int):
        self.cursor.execute(
            "INSERT OR REPLACE INTO mutes (user_id, chat_id, muted_until) VALUES (?, ?, ?)",
            (user_id, chat_id, until)
        )
        self.conn.commit()
    
    def remove_mute(self, user_id: int, chat_id: int):
        self.cursor.execute(
            "DELETE FROM mutes WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        self.conn.commit()
    
    def is_muted(self, user_id: int, chat_id: int) -> bool:
        self.cursor.execute(
            "SELECT muted_until FROM mutes WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        result = self.cursor.fetchone()
        if result:
            return result[0] > int(datetime.now().timestamp()) or result[0] == -1
        return False

mute_db = MuteDB()

# ===== ФУНКЦИИ OSINT =====
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

# ===== ПОИСКОВЫЕ ФУНКЦИИ =====
def search_wikipedia(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "extract" in data:
                return data
    except:
        pass
    return None

def search_ddg(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = f"https://api.duckduckgo.com/?q={query.replace(' ', '+')}&format=json&no_html=1&skip_disambig=1"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "AbstractText" in data and data["AbstractText"]:
                return {"source": "DuckDuckGo", "text": data["AbstractText"]}
    except:
        pass
    return None

def search_yandex(query):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        }
        url = f"https://yandex.ru/search/?text={query.replace(' ', '+')}&lr=213"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            desc_match = re.search(r'<div class="text-container">(.*?)</div>', r.text, re.DOTALL)
            if desc_match:
                return {"source": "Яндекс", "text": re.sub(r'<.*?>', '', desc_match.group(1))[:300]}
            alt_match = re.search(r'<span class="organic__text">(.*?)</span>', r.text, re.DOTALL)
            if alt_match:
                return {"source": "Яндекс", "text": re.sub(r'<.*?>', '', alt_match.group(1))[:300]}
    except:
        pass
    return None

def search_google(query):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        }
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=ru"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            desc_match = re.search(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if desc_match:
                return {"source": "Google", "text": desc_match.group(1)}
            alt_match = re.search(r'<span class="aCOpRe">(.*?)</span>', r.text)
            if alt_match:
                return {"source": "Google", "text": alt_match.group(1)}
    except:
        pass
    return None

def get_person_info(query):
    wiki_data = search_wikipedia(query)
    if wiki_data:
        return {"source": "Wikipedia", "data": wiki_data}
    
    ddg_data = search_ddg(query)
    if ddg_data:
        return ddg_data
    
    yandex_data = search_yandex(query)
    if yandex_data:
        return yandex_data
    
    google_data = search_google(query)
    if google_data:
        return google_data
    
    return None

async def smart_search(query, user_id):
    if is_banned(user_id):
        return {"personal": {"Ошибка": "❌ Вы были заблокированы администратором."}}

    result = {
        "personal": {},
        "phone": None,
        "email": None,
        "social": [],
        "breaches": 0,
        "description": None,
        "source": None,
        "wiki_data": None
    }

    # --- IP ---
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

    # --- Email ---
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

    # --- Номер телефона ---
    if re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query):
        phone = re.search(r'(\+?\d[\d\s\-\(\)]{7,15})', query).group(0).replace(" ", "").replace("-", "")
        result["phone"] = phone
        result["social"].append(f"📱 Telegram: https://t.me/+{phone}")
        result["social"].append(f"💬 WhatsApp: https://wa.me/{phone}")
        result["social"].append(f"💬 Viber: https://chats.viber.com/{phone}")
        return result

    # --- Поиск человека (ФИО) ---
    person_info = get_person_info(query)
    if person_info:
        result["source"] = person_info["source"]
        if "data" in person_info:
            result["wiki_data"] = person_info["data"]
            if "extract" in person_info["data"]:
                result["description"] = person_info["data"]["extract"]
        elif "text" in person_info:
            result["description"] = person_info["text"]

    # --- Соцсети ---
    platforms = {
        "Telegram": "https://t.me/{}",
        "Instagram": "https://instagram.com/{}",
        "VK": "https://vk.com/{}",
        "GitHub": "https://github.com/{}",
        "Twitter": "https://twitter.com/{}",
        "TikTok": "https://tiktok.com/@{}",
        "YouTube": "https://youtube.com/@{}",
        "Reddit": "https://reddit.com/user/{}",
        "Pinterest": "https://pinterest.com/{}",
        "Steam": "https://steamcommunity.com/id/{}",
        "Twitch": "https://twitch.tv/{}"
    }

    variants = [query, query.replace(" ", "_"), query.replace(" ", "")]
    for variant in variants:
        nick = variant.replace(" ", "_")
        for name, url_template in platforms.items():
            url = url_template.format(nick)
            try:
                r = requests.head(url, timeout=2)
                if r.status_code == 200:
                    result["social"].append(f"✅ {name}: {url}")
            except:
                pass

    if not result["description"] and not result["social"]:
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
        .footer {{ margin-top: 40px; color: #555; font-size: 12px; border-top: 1px solid #222; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">🌙 SMERTNY SEARCH | OSINT Report</div>
    <div class="sub">Запрос: {query}</div>
    <div class="sub">Пользователь: @{username} (ID: {user_id})</div>
    <div class="sub">Дата: {now}</div>
    <div class="category">📌 ИНФОРМАЦИЯ</div>
'''
    if data.get("source"):
        html += f'    <div class="item">📌 Источник: {data["source"]}</div>\n'
    if data.get("wiki_data") and "title" in data["wiki_data"]:
        html += f'    <div class="item">👤 Имя: {data["wiki_data"]["title"]}</div>\n'
    if data.get("description"):
        html += f'    <div class="item">📝 {data["description"]}</div>\n'
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
    <div class="category">🔗 СОЦИАЛЬНЫЕ СЕТИ</div>
'''
    if data.get("social"):
        for soc in data["social"][:20]:
            html += f'    <div class="item">{soc}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="footer">Источники: Wikipedia, DuckDuckGo, Яндекс, Google, HaveIBeenPwned, ip-api.com</div>
    <div class="footer">🌙 Smertny Search — ваш надёжный OSINT-инструмент</div>
</body>
</html>
'''
    return html, filename

# ===== КЛАВИАТУРЫ =====
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

# ===== ОСНОВНЫЕ КОМАНДЫ =====
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
        f"👋 Добро пожаловать в *Smertny Bot*!\n"
        f"📊 Осталось запросов: {balance}\n\n"
        f"🔍 Введите ФИО, IP, email, телефон или ник для поиска.\n"
        f"🛡️ Команды модерации работают в группах.\n\n"
        f"📌 Команды:\n"
        f".докс [запрос] - поиск информации\n"
        f".mute [@user] [минуты] - замутить\n"
        f".unmute [@user] - снять мут\n"
        f".spam [кол-во] [текст] - спам\n"
        f".admin - админ-панель",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ===== КОМАНДА .ДОКС =====
async def cmd_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без ника"
    ip = update.effective_user.link or "Неизвестно"
    set_user_ip(user_id, ip)

    if is_banned(user_id, ip):
        await update.message.reply_text("❌ Вы были заблокированы.")
        return

    if not context.args:
        await update.message.reply_text("❌ Использование: .докс [ФИО, IP, email, телефон]")
        return

    query = " ".join(context.args)

    if get_user_queries(user_id) <= 0:
        await update.message.reply_text("❌ Закончились запросы. Пополните баланс у администратора.")
        return

    if not use_query(user_id):
        await update.message.reply_text("❌ Ошибка при использовании запроса.")
        return

    search_msg = await update.message.reply_text("⏳ Поиск информации...")

    try:
        data = await smart_search(query, user_id)
        html, filename = generate_html_report(query, user_id, username, data)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        msg = "📊 *Результаты поиска*\n\n"

        if data.get("source"):
            msg += f"📌 *Источник:* {data['source']}\n"
        
        if data.get("wiki_data") and "title" in data["wiki_data"]:
            msg += f"👤 *Имя:* {data['wiki_data']['title']}\n"

        if data.get("description"):
            desc = data["description"][:500] + "..." if len(data["description"]) > 500 else data["description"]
            msg += f"📝 *Описание:*\n{desc}\n"

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

        msg += f"\n📄 *HTML-отчёт приложен*"

        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename=filename),
                caption=msg,
                parse_mode="Markdown"
            )
        os.remove(filename)
        await search_msg.delete()

    except Exception as e:
        add_queries(user_id, 1)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        await search_msg.delete()

# ===== КОМАНДЫ МОДЕРАЦИИ =====
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        await update.message.reply_text("❌ Команда работает только в группах!")
        return
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Использование: .mute [@user] [минуты]")
        return
    
    target = args[0].replace("@", "")
    duration = int(args[1]) if len(args) > 1 else None
    
    try:
        target_user = await context.bot.get_chat_member(update.message.chat.id, target) if target.startswith("@") else await context.bot.get_chat_member(update.message.chat.id, int(target))
        target_id = target_user.user.id
        
        until = -1 if duration is None else int((datetime.now() + timedelta(minutes=duration)).timestamp())
        mute_db.add_mute(target_id, update.message.chat.id, until)
        
        if duration:
            await update.message.reply_text(f"🔇 Пользователь замучен на {duration} минут!")
        else:
            await update.message.reply_text("🔇 Пользователь замучен навсегда!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        await update.message.reply_text("❌ Команда работает только в группах!")
        return
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Использование: .unmute [@user]")
        return
    
    target = args[0].replace("@", "")
    
    try:
        target_user = await context.bot.get_chat_member(update.message.chat.id, target) if target.startswith("@") else await context.bot.get_chat_member(update.message.chat.id, int(target))
        target_id = target_user.user.id
        
        if not mute_db.is_muted(target_id, update.message.chat.id):
            await update.message.reply_text("❌ Пользователь не в муте!")
            return
        
        mute_db.remove_mute(target_id, update.message.chat.id)
        await update.message.reply_text("✅ Мут снят!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def cmd_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        await update.message.reply_text("❌ Команда работает только в группах!")
        return
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Использование: .spam [кол-во] [текст]")
        return
    
    try:
        count = int(args[0])
        text = " ".join(args[1:])
        
        if count > 50:
            await update.message.reply_text("❌ Нельзя спамить больше 50 сообщений!")
            return
        
        await update.message.delete()
        for _ in range(min(count, 50)):
            await update.message.reply_text(text)
            await asyncio.sleep(0.3)
    except:
        await update.message.reply_text("❌ Ошибка в команде")

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав!")
        return
    
    await update.message.reply_text(
        "⚙️ *Админ-панель*\n\n"
        "📌 Команды OSINT:\n"
        "/give @username кол-во - выдать запросы\n"
        "/steal @username кол-во - забрать запросы\n"
        "/block @username - заблокировать\n"
        "/unblock @username - разблокировать\n"
        "/banlist - список заблокированных\n"
        "/setlimit кол-во - установить лимит\n"
        "/broadcast сообщение - рассылка\n\n"
        "📌 Команды модерации:\n"
        ".mute [@user] [минуты] - мут\n"
        ".unmute [@user] - снять мут\n"
        ".spam [кол-во] [текст] - спам",
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
    await update.message.reply_text(f"✅ Лимит запросов установлен на {limit}")

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

# ===== ОБРАБОТКА СООБЩЕНИЙ (AUTO-MUTE) =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    
    if mute_db.is_muted(user_id, chat_id):
        try:
            await update.message.delete()
        except:
            pass
        return

# ===== INLINE МЕНЮ =====
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
            "🔍 *Поиск*\n\nОтправьте мне ФИО, IP, email, телефон или ник",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "profile":
        balance = get_user_queries(user_id)
        registered = users.get(user_id, {}).get("registered", "Неизвестно")
        ip = get_user_ip(user_id)
        await query.edit_message_text(
            f"👤 *Профиль*\n\n🆔 ID: {user_id}\n📊 Осталось: {balance}\n📅 Регистрация: {registered}\n🌐 IP: {ip}",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "checks":
        await query.edit_message_text(
            "✅ *Чекки*\n\n• ФИО — Wikipedia, DuckDuckGo, Яндекс, Google\n• IP — геолокация\n• Email — проверка утечек\n• Телефон — проверка в Telegram",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
    elif data == "support":
        await query.edit_message_text("🆘 Владелец: @okimdeadlybutimnotteamsandidmeok", reply_markup=back_button())
    elif data == "admin":
        await query.edit_message_text(
            "⚙️ *Админ-панель*\n\n/give @username кол-во\n/steal @username кол-во\n/block @username\n/unblock @username\n/banlist\n/setlimit кол-во\n/broadcast сообщение",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )

# ===== ЗАПУСК =====
app = Application.builder().token(TOKEN).build()

# Команды
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("give", give_queries))
app.add_handler(CommandHandler("steal", steal_queries))
app.add_handler(CommandHandler("block", block_user))
app.add_handler(CommandHandler("unblock", unblock_user))
app.add_handler(CommandHandler("banlist", banlist))
app.add_handler(CommandHandler("setlimit", set_limit))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("admin", cmd_admin))

# Команды с точкой
app.add_handler(CommandHandler("докс", cmd_docs))
app.add_handler(CommandHandler("mute", cmd_mute))
app.add_handler(CommandHandler("unmute", cmd_unmute))
app.add_handler(CommandHandler("spam", cmd_spam))

# Обработчики
app.add_handler(CallbackQueryHandler(menu_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🚀 Smertny Bot запущен!")
app.run_polling()
