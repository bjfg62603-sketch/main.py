import logging
import re
import requests
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== ТОКЕН =====
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"

# ===== ЛОГИ =====
logging.basicConfig(level=logging.INFO)

# ===== ХРАНИЛИЩЕ =====
users = {}       # user_id: {"queries": int, "username": str, "first_name": str}
checks = {}      # code: {"name": str, "queries": int, "activations": int, "used_by": []}

# ===== ФУНКЦИИ БАЛАНСА =====
def get_user_queries(user_id):
    return users.get(user_id, {}).get("queries", 0)

def add_queries(user_id, amount):
    if user_id not in users:
        users[user_id] = {"queries": 0, "username": str(user_id), "first_name": "Пользователь"}
    users[user_id]["queries"] += amount

def use_query(user_id):
    if user_id in users and users[user_id]["queries"] > 0:
        users[user_id]["queries"] -= 1
        return True
    return False

def get_user_identifier(user_id):
    data = users.get(user_id, {})
    username = data.get("username")
    first_name = data.get("first_name", "Пользователь")
    return f"@{username}" if username and username != str(user_id) else first_name

# ===== ГЕНЕРАЦИЯ КОДА =====
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

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    first_name = update.effective_user.first_name or "Пользователь"
    
    if user_id not in users:
        users[user_id] = {"queries": 5, "username": username, "first_name": first_name}
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

# ===== МЕНЮ =====
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "search":
        await query.edit_message_text(
            "🔍 Отправьте мне:\n- IP\n- Email\n- Ник\n- Любой текст для поиска",
            reply_markup=main_menu()
        )
    elif data == "profile":
        balance = get_user_queries(user_id)
        await query.edit_message_text(
            f"👤 Ваш профиль\n📊 Осталось запросов: {balance}",
            reply_markup=main_menu()
        )
    elif data == "checks":
        await query.edit_message_text(
            "✅ Чекки:\n- Email — проверка утечек\n- IP — геолокация\n- Ник — поиск по соцсетям",
            reply_markup=main_menu()
        )
    elif data == "support":
        await query.edit_message_text(
            "🆘 Поддержка\nВладелец: @okimdeadlybutimnotteamsandidmeok",
            reply_markup=main_menu()
        )
    elif data == "admin":
        await query.edit_message_text(
            "⚙️ Админ-панель\nКоманды:\n/give @username кол-во\n/steal @username кол-во\n/deletecheck КОД\n/createcheck Название запросы активации",
            reply_markup=main_menu()
        )

# ===== ПОИСК =====
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

    if re.match(r'\d+\.\d+\.\d+\.\d+', text):
        try:
            r = requests.get(f"http://ip-api.com/json/{text}").json()
            if r['status'] == 'success':
                await update.message.reply_text(
                    f"🌍 IP: {text}\n📍 {r['city']}, {r['country']}\n📡 {r['isp']}",
                    reply_markup=main_menu()
                )
                return
        except:
            pass
        await update.message.reply_text("❌ IP не найден.", reply_markup=main_menu())
        return

    if '@' in text:
        await update.message.reply_text(f"📧 Email: {text}\n🔍 Проверка утечек... (заглушка)", reply_markup=main_menu())
        return

    await update.message.reply_text(f"✅ Получено: {text}\n🔍 Ищу... (заглушка)", reply_markup=main_menu())

# ===== АДМИН: ВЫДАЧА =====
async def give_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 8428048355:
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

# ===== АДМИН: ЗАБОР =====
async def steal_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 8428048355:
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
            await update.message.reply_text(f"✅ Забрано {amount} запросов у {get_user_identifier(uid)}.")
            return
    await update.message.reply_text("❌ Пользователь не найден.")

# ===== АДМИН: БАЛАНС =====
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 8428048355:
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

# ===== АДМИН: СОЗДАНИЕ ЧЕКА =====
async def create_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 8428048355:
        await update.message.reply_text("⛔ Только владелец.")
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ /createcheck Название кол-во_запросов кол-во_активаций")
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
    await update.message.reply_text(f"✅ Чек создан!\n📌 Название: {name}\n🎫 Код: {code}\n📊 Запросов: {queries}\n🔄 Активаций: {activations}")

# ===== АДМИН: УДАЛЕНИЕ ЧЕКА =====
async def delete_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 8428048355:
        await update.message.reply_text("⛔ Только владелец.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /deletecheck КОД")
        return
    code = args[0].upper()
    if code in checks:
        del checks[code]
        await update.message.reply_text(f"✅ Чек {code} удалён.")
    else:
        await update.message.reply_text("❌ Чек не найден.")

# ===== АКТИВАЦИЯ ЧЕКА (для всех) =====
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
