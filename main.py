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

# ===== ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ =====
def get_user_ip(user_id):
    return user_ips.get(user_id, "Неизвестно")

def set_user_ip(user_id, ip):
    user_ips[user_id] = ip
    save_data()

# ===== ПРОВЕРКА БАНА =====
def is_banned(user_id, ip=None):
    if user_id in banned_users:
        return True
    if ip and ip in banned_ips:
        return True
    return False

# ===== ПОИСК ПОЛЬЗОВАТЕЛЯ ПО USERNAME =====
def find_user_by_username(username):
    username = username.replace("@", "")
    for uid, data in users.items():
        if data.get("username") == username:
            return uid
    return None

# ===== ОСНОВНАЯ ЛОГИКА ПОИСКА (С ПРОВЕРКОЙ БАНА) =====
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
        "wikipedia": None
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
        return result

    # --- Поиск человека (ФИО) ---
    # Используем DuckDuckGo для быстрого поиска
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={query.replace(' ', '+')}&format=json&no_html=1&skip_disambig=1"
        r = requests.get(ddg_url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "AbstractText" in data and data["AbstractText"]:
                result["description"] = data["AbstractText"][:300] + "..."
    except:
        pass

    # --- Википедия ---
    try:
        wiki_url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        r = requests.get(wiki_url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "extract" in data:
                result["wikipedia"] = data["extract"][:500] + "..."
    except:
        pass

    # --- Соцсети ---
    nick = query.replace(" ", "_")
    socials = {
        "Telegram": f"https://t.me/{nick}",
        "Instagram": f"https://instagram.com/{nick}",
        "VK": f"https://vk.com/{nick}",
        "GitHub": f"https://github.com/{nick}",
        "Twitter": f"https://twitter.com/{nick}",
        "TikTok": f"https://tiktok.com/@{nick}",
        "YouTube": f"https://youtube.com/@{nick}"
    }
    for name, url in socials.items():
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200:
                result["social"].append(f"✅ {name}: {url}")
        except:
            pass

    if not result["description"] and not result["wikipedia"] and not result["social"]:
        result["personal"]["Информация"] = "❌ Ничего не найдено. Попробуйте уточнить запрос."

    return result

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

        msg = f"📊 *Найдено по запросу:*\n\n"
        if data.get("description"):
            msg += f"🔍 {data['description']}\n\n"
        if data.get("wikipedia"):
            msg += f"📚 {data['wikipedia'][:300]}...\n\n"
        if data.get("phone"):
            msg += f"📱 Телефон: {data['phone']}\n"
        if data.get("email"):
            msg += f"📧 Email: {data['email']}\n"
        if data.get("breaches") and data["breaches"] > 0:
            msg += f"🔴 Утечки: {data['breaches']}\n"
        if data.get("social"):
            msg += f"\n🔗 Соцсети: {len(data['social'])} найдено"
        msg += f"\n\n📄 HTML-отчёт приложен"

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
    if data.get("description"):
        html += f'    <div class="item">🔍 {data["description"]}</div>\n'
    if data.get("wikipedia"):
        html += f'    <div class="item">📚 {data["wikipedia"]}</div>\n'
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
        for soc in data["social"][:10]:
            html += f'    <div class="item">{soc}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="footer">Источники: Google, Яндекс, DuckDuckGo, Wikipedia, VK API, HaveIBeenPwned, ip-api.com</div>
    <div class="footer">🌙 Smertnyy Search — ваш надёжный OSINT-инструмент</div>
</body>
</html>
'''
    return html, filename

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
        f"🔍 Введите ФИО, IP, email, телефон или ник.\n"
        f"📌 Бот ищет в Google, Яндекс, DuckDuckGo, Wikipedia и соцсетях.",
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
            f"👋 Главное меню\n📊 Осталось запросов: {balance}",
            reply_markup=main_menu()
        )
    elif data == "search":
        await query.edit_message_text(
            "🔍 *Поиск*\n\n"
            "Отправьте мне:\n"
            "• ФИО или ник\n"
            "• IP-адрес\n"
            "• Email\n"
            "• Номер телефона",
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
            "• ФИО — поиск в Google, Яндекс, DuckDuckGo, Wikipedia, соцсетях\n"
            "• IP — геолокация, провайдер\n"
            "• Email — проверка утечек\n"
            "• Телефон — проверка в Telegram",
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
            "/broadcast сообщение",
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
app.add_handler(CommandHandler("activate", activate_check))
app.add_handler(CallbackQueryHandler(menu_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🚀 Smertnyy Search запущен")
app.run_polling()
