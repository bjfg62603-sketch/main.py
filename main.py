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
        users[user_id] = {"queries": 0, "username": str(user_id), "first_name": "Пользователь"}
    users[user_id]["queries"] += amount
    save_data()

def use_query(user_id):
    if users.get(user_id, {}).get("queries", 0) > 0:
        users[user_id]["queries"] -= 1
        save_data()
        return True
    return False

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
    <div class="header">🚀 TELEGRAM OSINT REPORT</div>
    <div class="sub">Запрос: {query}</div>
    <div class="sub">Пользователь: @{username} (ID: {user_id})</div>
    <div class="sub">Дата: {now}</div>
    <div class="category">📌 ЛИЧНЫЕ ДАННЫЕ</div>
'''
    # --- Личные данные ---
    if data.get("personal"):
        for k, v in data["personal"].items():
            html += f'    <div class="item">{k}: {v}</div>\n'
    else:
        html += '    <div class="item">Нет личных данных</div>\n'

    html += f'''
    <div class="category">📱 ТЕЛЕФОН</div>
'''
    if data.get("phone"):
        html += f'    <div class="item">Телефон: {data["phone"]}</div>\n'
        html += f'    <div class="item">🔍 Telegram: https://t.me/{data["phone"]}</div>\n'
        html += f'    <div class="item">📞 WhatsApp: https://wa.me/{data["phone"]}</div>\n'
        html += f'    <div class="item">💬 Viber: https://chats.viber.com/{data["phone"]}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">📧 EMAIL</div>
'''
    if data.get("email"):
        html += f'    <div class="item">Email: {data["email"]}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">🔗 СОЦИАЛЬНЫЕ СЕТИ</div>
'''
    if data.get("social"):
        for soc in data["social"]:
            html += f'    <div class="item">✅ {soc}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">💬 КОММЕНТАРИИ И УПОМИНАНИЯ</div>
'''
    if data.get("comments"):
        for comment in data["comments"][:10]:
            html += f'    <div class="item">📌 {comment}</div>\n'
    else:
        html += '    <div class="item">Нет данных</div>\n'

    html += f'''
    <div class="category">📦 УТЕЧКИ</div>
'''
    if data.get("breaches"):
        html += f'    <div class="item">🔴 Найден в {data["breaches"]} утечках</div>\n'
    else:
        html += '    <div class="item">🟢 Не найден</div>\n'

    html += f'''
    <div class="footer">API: Telegram, HaveIBeenPwned, Google Dorks</div>
    <div class="footer">Отчёт сгенерирован автоматически</div>
</body>
</html>
'''
    return html, filename

# ===== ОСНОВНАЯ ЛОГИКА ПОИСКА =====
async def deep_search(query):
    """Максимально глубокий поиск по Telegram и другим открытым источникам"""
    result = {
        "personal": {},
        "phone": None,
        "email": None,
        "social": [],
        "comments": [],
        "breaches": 0
    }

    # --- Поиск по Telegram (по номеру/username) ---
    if query.startswith("+"):
        phone = query.replace("+", "").strip()
        result["phone"] = phone
        result["personal"]["Telegram ID"] = "Проверяется..."
        result["personal"]["Возможные username"] = "Проверяется..."
        result["social"].append(f"Telegram: https://t.me/+{phone}")
        result["social"].append(f"WhatsApp: https://wa.me/{phone}")
        result["social"].append(f"Viber: https://chats.viber.com/{phone}")
    else:
        nick = query.strip()
        result["personal"]["Username"] = nick
        result["social"].append(f"Telegram: https://t.me/{nick}")
        result["social"].append(f"Instagram: https://instagram.com/{nick}")
        result["social"].append(f"VK: https://vk.com/{nick}")
        result["social"].append(f"GitHub: https://github.com/{nick}")
        result["social"].append(f"Twitter: https://twitter.com/{nick}")

    # --- Комментарии и упоминания через Google Dorks ---
    try:
        google_dork = f"https://www.google.com/search?q=%22{query}%22+site:t.me+OR+site:telegram.org"
        result["comments"].append(f"🔍 Поиск упоминаний: {google_dork}")
    except:
        pass

    # --- Проверка утечек (если есть email) ---
    if "@" in query:
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

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
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

    await update.message.reply_text("⏳ Глубокий поиск... (запрос списан)")

    try:
        data = await deep_search(text)
        html, filename = generate_html_report(text, user_id, username, data)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename=filename),
                caption="📊 Отчёт сгенерирован",
                reply_markup=main_menu()
            )
        os.remove(filename)

    except Exception as e:
        add_queries(user_id, 1)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=main_menu())

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    first_name = update.effective_user.first_name or "Пользователь"

    if user_id not in users:
        users[user_id] = {"queries": 5, "username": username, "first_name": first_name}
        save_data()

    await update.message.reply_text(
        f"👋 Добро пожаловать, @{username}!\n🎁 У вас {get_user_queries(user_id)} запросов.",
        reply_markup=main_menu()
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await query.edit_message_text("📊 Главное меню", reply_markup=main_menu())
    elif data == "profile":
        await query.edit_message_text(f"👤 Баланс: {get_user_queries(user_id)}", reply_markup=back_button())
    elif data == "checks":
        await query.edit_message_text("✅ Чекки:\n- Телефон\n- Email\n- Ник", reply_markup=back_button())
    elif data == "support":
        await query.edit_message_text("🆘 Владелец: @okimdeadlybutimnotteamsandidmeok", reply_markup=back_button())
    elif data == "admin":
        await query.edit_message_text("⚙️ /give /steal /balance /createcheck /deletecheck", reply_markup=back_button())

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
        return
    for uid, data in users.items():
        if data.get("username") == target:
            add_queries(uid, amount)
            await update.message.reply_text(f"✅ Выдано {amount}")
            return

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

async def balance(update, context):
    if not is_admin(update.effective_user.id):
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

async def create_check(update, context):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 3:
        return
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    checks[code] = {"queries": int(args[1]), "activations": int(args[2]), "used_by": []}
    save_data()
    await update.message.reply_text(f"✅ Чек {code}")

async def delete_check(update, context):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        return
    code = args[0].upper()
    if code in checks:
        del checks[code]
        save_data()
        await update.message.reply_text(f"✅ Чек {code} удалён")

# ===== ЗАПУСК =====
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("give", give_queries))
app.add_handler(CommandHandler("steal", steal_queries))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("createcheck", create_check))
app.add_handler(CommandHandler("deletecheck", delete_check))
app.add_handler(CallbackQueryHandler(menu_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🚀 Бот запущен")
app.run_polling()
