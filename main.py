import logging
import re
import requests
import random
import string
import json
import os
import hashlib
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== ТОКЕН =====
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"

# ===== КТО МОЖЕТ ИСПОЛЬЗОВАТЬ АДМИН-КОМАНДЫ =====
ADMIN_IDS = [8428048355]  # твой ID

# ===== ЛОГИ =====
logging.basicConfig(level=logging.INFO)

# ===== ФАЙЛ ДЛЯ ХРАНЕНИЯ ДАННЫХ =====
DATA_FILE = "data.json"

# ===== ЗАГРУЗКА / СОХРАНЕНИЕ =====
def load_data():
    global users, checks
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                users = data.get("users", {})
                checks = data.get("checks", {})
                users = {int(k): v for k, v in users.items()}
                return
        except:
            pass
    users = {}
    checks = {}

def save_data():
    try:
        users_str_keys = {str(k): v for k, v in users.items()}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": users_str_keys, "checks": checks}, f, ensure_ascii=False, indent=2)
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
    if user_id in users and users[user_id]["queries"] > 0:
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

# ===== КОМАНДА /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    first_name = update.effective_user.first_name or "Пользователь"

    if user_id not in users:
        users[user_id] = {"queries": 5, "username": username, "first_name": first_name}
        save_data()
        await update.message.reply_text(
            f"👋 Добро пожаловать, {get_user_identifier(user_id)}!\n🎁 Вам начислено 5 запросов.",
            reply_markup=main_menu()
        )
    else:
        balance = get_user_queries(user_id)
        await update.message.reply_text(
            f"👋 С возвращением, {get_user_identifier(user_id)}!\n📊 Осталось запросов: {balance}",
            reply_markup=main_menu()
        )

# ===== ОБРАБОТЧИК МЕНЮ =====
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        balance = get_user_queries(user_id)
        await query.edit_message_text(
            f"👋 Вы в главном меню.\n📊 Осталось запросов: {balance}",
            reply_markup=main_menu()
        )
    elif data == "search":
        await query.edit_message_text(
            "🔍 Отправьте мне:\n- IP\n- Email\n- Ник\n- Любой текст для поиска",
            reply_markup=back_button()
        )
    elif data == "profile":
        balance = get_user_queries(user_id)
        await query.edit_message_text(
            f"👤 Ваш профиль\n📊 Осталось запросов: {balance}",
            reply_markup=back_button()
        )
    elif data == "checks":
        await query.edit_message_text(
            "✅ Чекки:\n- Email — проверка утечек\n- IP — геолокация\n- Ник — поиск по соцсетям",
            reply_markup=back_button()
        )
    elif data == "support":
        await query.edit_message_text(
            "🆘 Поддержка\nВладелец: @okimdeadlybutimnotteamsandidmeok",
            reply_markup=back_button()
        )
    elif data == "admin":
        await query.edit_message_text(
            "⚙️ Админ-панель\nКоманды:\n/give @username кол-во\n/steal @username кол-во\n/deletecheck КОД\n/createcheck Название запросы активации",
            reply_markup=back_button()
        )

# ===== РЕАЛЬНЫЙ ПОИСК =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if get_user_queries(user_id) <= 0:
        await update.message.reply_text("❌ У вас закончились запросы.", reply_markup=main_menu())
        return

    if not use_query(user_id):
        await update.message.reply_text("❌ Ошибка: недостаточно запросов.")
        return

    await update.message.reply_text("⏳ Поиск... (запрос списан)")

    # --- IP ---
    if re.match(r'\d+\.\d+\.\d+\.\d+', text):
        try:
            r = requests.get(f"http://ip-api.com/json/{text}", timeout=5).json()
            if r.get('status') == 'success':
                await update.message.reply_text(
                    f"🌍 IP: {text}\n📍 {r.get('city', '')}, {r.get('country', '')}\n📡 {r.get('isp', '')}",
                    reply_markup=main_menu()
                )
                return
        except:
            pass
        await update.message.reply_text("❌ IP не найден.", reply_markup=main_menu())
        return

    # --- Email ---
    if '@' in text:
        email = text.strip()
        try:
            sha1 = hashlib.sha1(email.encode()).hexdigest().upper()
            prefix, suffix = sha1[:5], sha1[5:]
            r = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
            breaches = 0
            for line in r.text.splitlines():
                if line.startswith(suffix):
                    breaches = int(line.split(':')[1])
                    break
            msg = f"📧 Email: {email}\n"
            msg += f"🔴 Найден в {breaches} утечках" if breaches > 0 else "🟢 Не найден в утечках"
            await update.message.reply_text(msg, reply_markup=main_menu())
        except:
            await update.message.reply_text(f"📧 Email: {email}\n⚠️ Проверка утечек недоступна", reply_markup=main_menu())
        return

    # --- Соцсети (поиск ника) ---
    nick = text.strip()
    platforms = {
        "Telegram": f"https://t.me/{nick}",
        "Instagram": f"https://instagram.com/{nick}",
        "VK": f"https://vk.com/{nick}",
        "GitHub": f"https://github.com/{nick}",
        "Twitter": f"https://twitter.com/{nick}",
        "TikTok": f"https://tiktok.com/@{nick}",
        "YouTube": f"https://youtube.com/@{nick}",
        "Reddit": f"https://reddit.com/user/{nick}",
    }
    found = []
    for name, url in platforms.items():
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200:
                found.append(f"✅ {name}: {url}")
        except:
            pass
    if found:
        await update.message.reply_text(f"🆔 Ник: {nick}\n" + "\n".join(found), reply_markup=main_menu())
    else:
        await update.message.reply_text(f"❌ По нику {nick} ничего не найдено.", reply_markup=main_menu())

# ===== ПРОВЕРКА АДМИНА =====
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===== АДМИН-КОМАНДЫ =====
async def give_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только владелец.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ /give @username кол-во")
        return
    target = args[0].replace("@", "")
    try:
        amount = int(args[1])
    except:
        await update.message.reply_text("❌ Количество должно быть числом.")
        return
    for uid, data in users.items():
        if data.get("username") == target or str(uid) == target:
            add_queries(uid, amount)
            await update.message.reply_text(f"✅ Выдано {amount} запросов пользователю {get_user_identifier(uid)}.")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

async def steal_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только владелец.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ /steal @username кол-во")
        return
    target = args[0].replace("@", "")
    try:
        amount = int(args[1])
    except:
        await update.message.reply_text("❌ Количество должно быть числом.")
        return
    for uid, data in users.items():
        if data.get("username") == target or str(uid) == target:
            current = get_user_queries(uid)
            if current < amount:
                await update.message.reply_text(f"❌ У пользователя только {current} запросов.")
                return
            users[uid]["queries"] -= amount
            save_data()
            await update.message.reply_text(f"✅ Забрано {amount} запросов у {get_user_identifier(uid)}.")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только владелец.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /balance @username")
        return
    target = args[0].replace("@", "")
    for uid, data in users.items():
        if data.get("username") == target or str(uid) == target:
            await update.message.reply_text(f"📊 Баланс {get_user_identifier(uid)}: {get_user_queries(uid)} запросов.")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

async def create_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только владелец.")
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ /createcheck Название запросы активации")
        return
    name = args[0]
    try:
        queries = int(args[1])
        activations = int(args[2])
    except:
        await update.message.reply_text("❌ Числа должны быть числами.")
        return
    code = generate_code()
    checks[code] = {"name": name, "queries": queries, "activations": activations, "used_by": []}
    save_data()
    await update.message.reply_text(f"✅ Чек создан!\n📌 Название: {name}\n🎫 Код: {code}\n📊 Запросов: {queries}\n🔄 Активаций: {activations}")

async def delete_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только владелец.")
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

async def activate_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if user_id in check["used_by"]:
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
    await update.message.reply_text(f"✅ Активирован чек {code}!\n📊 Получено {check['queries']} запросов.")

# ===== РЕГИСТРАЦИЯ =====
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

print("🚀 Бот запущен")
app.run_polling()
