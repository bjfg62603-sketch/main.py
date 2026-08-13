import os
import sqlite3
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8428048355))

print("🚀 БОТ ЗАПУЩЕН!")

conn = sqlite3.connect("moderator.db", check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS muted (chat_id INTEGER, user_id INTEGER, until TEXT, PRIMARY KEY (chat_id, user_id))""")
c.execute("""CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, reason TEXT, date TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS messages (message_id INTEGER, chat_id INTEGER, user_id INTEGER, text TEXT, date TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS saved (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, file_id TEXT, file_type TEXT, caption TEXT, date TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
c.execute("INSERT OR IGNORE INTO settings VALUES ('max_warns', '5')")
conn.commit()
print("✅ БАЗА ДАННЫХ ГОТОВА")

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_user_link(user):
    if user.username:
        return f"@{user.username}"
    else:
        return f"[{user.full_name}](tg://user?id={user.id})"

# ============================================
# .DEL — УДАЛЯЕТ СООБЩЕНИЕ И СВОЮ КОМАНДУ
# ============================================
def del_msg(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("⛔ Только админ!")
        return

    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение, которое хочешь удалить!")
        return

    target = update.message.reply_to_message
    chat_id = update.message.chat.id
    msg_id = target.message_id

    try:
        update.message.delete()
    except:
        pass

    try:
        context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        update.message.reply_text("🗑️ **Сообщение удалено!**", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")

# ============================================
# .MUTE — МУТИТ + УДАЛЯЕТ СООБЩЕНИЕ
# ============================================
def mute(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id

    if not is_admin(user_id):
        update.message.reply_text("⛔ Только админ!")
        return

    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение человека, которого хочешь замутить!")
        return

    target = update.message.reply_to_message.from_user
    target_msg = update.message.reply_to_message

    if target.id == user_id:
        update.message.reply_text("❌ Нельзя замутить себя!")
        return

    if target.id == context.bot.id:
        update.message.reply_text("❌ Нельзя замутить бота!")
        return

    target_id = target.id
    target_msg_id = target_msg.message_id

    args = context.args
    until = None
    minutes = 0
    if args:
        try:
            minutes = int(args[0].replace('m', ''))
            until = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass

    c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, ?)", (chat_id, target_id, until))
    conn.commit()

    try:
        update.message.delete()
    except:
        pass

    # УДАЛЯЕМ СООБЩЕНИЕ, НА КОТОРОЕ ОТВЕТИЛИ
    try:
        context.bot.delete_message(chat_id=chat_id, message_id=target_msg_id)
    except Exception as e:
        print(f"❌ Не удалось удалить сообщение: {e}")

    mute_text = f"🔇 {get_user_link(target)} ЗАМУЧЕН!"
    if until:
        mute_text += f" на {minutes} мин."

    update.message.reply_text(mute_text, parse_mode="Markdown")

# ============================================
# .UNMUTE
# ============================================
def unmute(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id

    if not is_admin(user_id):
        update.message.reply_text("⛔ Только админ!")
        return

    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение человека, которого хочешь размутить!")
        return

    target = update.message.reply_to_message.from_user

    if target.id == user_id:
        update.message.reply_text("❌ Нельзя размутить себя!")
        return

    target_id = target.id

    c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, target_id))
    conn.commit()

    try:
        update.message.delete()
    except:
        pass

    update.message.reply_text(f"🔊 {get_user_link(target)} РАЗМУЧЕН!", parse_mode="Markdown")

# ============================================
# .WARN
# ============================================
def warn(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id

    if not is_admin(user_id):
        update.message.reply_text("⛔ Только админ!")
        return

    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение человека!")
        return

    target = update.message.reply_to_message.from_user

    if target.id == user_id:
        update.message.reply_text("❌ Нельзя выдать варн себе!")
        return

    target_id = target.id
    args = context.args
    reason = " ".join(args) or "Без причины"

    c.execute("INSERT INTO warns (chat_id, user_id, reason, date) VALUES (?, ?, ?, datetime('now'))", (chat_id, target_id, reason))
    conn.commit()

    c.execute("SELECT COUNT(*) FROM warns WHERE chat_id=? AND user_id=?", (chat_id, target_id))
    warns_count = c.fetchone()[0]

    c.execute("SELECT value FROM settings WHERE key='max_warns'")
    max_warns = int(c.fetchone()[0])

    try:
        update.message.delete()
    except:
        pass

    if warns_count >= max_warns:
        c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, NULL)", (chat_id, target_id))
        conn.commit()
        update.message.reply_text(f"🔇 {get_user_link(target)} АВТО-МУТ ({warns_count} варнов)", parse_mode="Markdown")
    else:
        update.message.reply_text(f"⚠️ {get_user_link(target)} ВАРН {warns_count}/{max_warns}. Причина: {reason}", parse_mode="Markdown")

# ============================================
# .SAVE
# ============================================
def save_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("⛔ Только админ!")
        return

    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение, которое хочешь сохранить!")
        return

    reply = update.message.reply_to_message
    chat_id = update.message.chat.id

    file_id = None
    file_type = "text"
    caption = reply.caption or ""
    text = reply.text or ""

    if reply.photo:
        file_id = reply.photo[-1].file_id
        file_type = "photo"
        caption = reply.caption or ""
    elif reply.video:
        file_id = reply.video.file_id
        file_type = "video"
        caption = reply.caption or ""
    elif reply.document:
        file_id = reply.document.file_id
        file_type = "document"
        caption = reply.caption or ""
    elif reply.voice:
        file_id = reply.voice.file_id
        file_type = "voice"
    elif reply.text:
        file_id = None
        file_type = "text"
        text = reply.text or ""
    else:
        update.message.reply_text("❌ Этот тип нельзя сохранить!")
        return

    c.execute("INSERT INTO saved (chat_id, user_id, file_id, file_type, caption, date) VALUES (?, ?, ?, ?, ?, datetime('now'))", (chat_id, user_id, file_id, file_type, caption or text))
    conn.commit()

    try:
        update.message.delete()
    except:
        pass

    update.message.reply_text(f"💾 **СОХРАНЕНО!**\nТип: {file_type}\nID: {c.lastrowid}\n\n📌 Используй .get {c.lastrowid}", parse_mode="Markdown")

# ============================================
# ОСТАЛЬНЫЕ КОМАНДЫ (сокращены)
# ============================================
def saved_list_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    c.execute("SELECT id, file_type, caption, date FROM saved WHERE chat_id=? OR user_id=? ORDER BY date DESC LIMIT 10", (chat_id, user_id))
    saved = c.fetchall()
    if not saved:
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("📂 Сохранённых нет", reply_markup=reply_markup)
        return
    text = "📂 **Сохранённые:**\n\n"
    for item in saved:
        item_id, file_type, caption, date = item
        caption_preview = caption[:30] if caption else "(без текста)"
        text += f"• #{item_id} [{file_type}] {caption_preview}... ({date})\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

def get_saved(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: .get 1")
        return
    try:
        item_id = int(args[0])
        c.execute("SELECT file_id, file_type, caption FROM saved WHERE id=?", (item_id,))
        result = c.fetchone()
        if not result:
            update.message.reply_text(f"❌ ID {item_id} не найден!")
            return
        file_id, file_type, caption = result
        if file_type == "photo":
            update.message.reply_photo(file_id, caption=caption or "")
        elif file_type == "video":
            update.message.reply_video(file_id, caption=caption or "")
        elif file_type == "document":
            update.message.reply_document(file_id, caption=caption or "")
        elif file_type == "voice":
            update.message.reply_voice(file_id, caption=caption or "")
        elif file_type == "text":
            update.message.reply_text(f"📝 {caption}")
        else:
            update.message.reply_text(f"Тип: {file_type}")
    except:
        update.message.reply_text("❌ Ошибка!")

def mutelist(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    c.execute("SELECT user_id, until FROM muted WHERE chat_id=?", (chat_id,))
    muted = c.fetchall()
    if not muted:
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("📋 Нет замученных", reply_markup=reply_markup)
        return
    text = "📋 **ЗАМУЧЕННЫЕ:**\n\n"
    for uid, until in muted:
        try:
            user = context.bot.get_chat(uid)
            name = get_user_link(user)
        except:
            name = f"ID:{uid}"
        until_text = f" до {until}" if until else " (навсегда)"
        text += f"• {name}{until_text}\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

def spam(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("❌ .spam 5 текст")
        return
    try:
        count = int(args[0])
        if count > 20:
            count = 20
        text = " ".join(args[1:])
        try:
            update.message.delete()
        except:
            pass
        for _ in range(count):
            update.message.reply_text(text)
    except:
        update.message.reply_text("❌ Ошибка!")

def coin(update: Update, context: CallbackContext):
    update.message.reply_text(f"🎲 {random.choice(['Орёл', 'Решка'])}!")

def dice(update: Update, context: CallbackContext):
    result = random.randint(1, 6)
    emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    update.message.reply_text(f"🎲 {emojis[result-1]} {result}!")

def flip(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ .flip текст")
        return
    update.message.reply_text(f"🔄 { ' '.join(args)[::-1] }")

def quote(update: Update, context: CallbackContext):
    quotes = ["💭 Жизнь — это то, что происходит, пока ты строишь планы.", "💭 Будь собой, все остальные роли уже заняты.", "💭 Успех — это умение двигаться от неудачи к неудаче.", "💭 Лучший способ предсказать будущее — создать его."]
    update.message.reply_text(random.choice(quotes))

def plove(update: Update, context: CallbackContext):
    args = context.args
    count = int(args[0]) if args and args[0].isdigit() else 5
    if count > 20:
        count = 20
    update.message.reply_text("❤️" * count)

def spoiler(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ .spoiler текст")
        return
    update.message.reply_text(f"||{' '.join(args)}||", parse_mode="MarkdownV2")

def print_cmd(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ .print текст")
        return
    try:
        update.message.delete()
    except:
        pass
    update.message.reply_text(" ".join(args))

def joke(update: Update, context: CallbackContext):
    jokes = ["😂 Встречаются два программиста: — У тебя есть 5 рублей? — Да. — А у меня есть 10. Давай скинемся по 5 и купим пиццу?", "😂 — Почему программисты не любят природу? — Слишком много багов.", "😂 Как отличить бота от человека? Бот ответит сразу, человек — через 5 минут с извинениями."]
    update.message.reply_text(random.choice(jokes))

def leet(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ .leet текст")
        return
    leet_map = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7', 'b': '8', 'g': '9'}
    text = ' '.join(args)
    result = ''.join(leet_map.get(c.lower(), c) if c.isalpha() else c for c in text)
    update.message.reply_text(f"🧠 {result}")

def trol(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ .trol текст")
        return
    update.message.reply_text(f"🎭 {' '.join(args).swapcase()}")

def agro(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ .agro текст")
        return
    update.message.reply_text(f"🔊 {' '.join(args).upper()}!!1")

# ============================================
# МЕНЮ
# ============================================
def main_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🎮 Все команды", callback_data="all_commands")],
        [InlineKeyboardButton("💾 Сохранённое", callback_data="saved_list")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🌟 **SMERTNYTEAM BOT V9.0**\n\n🔥 **.MUTE ТЕПЕРЬ УДАЛЯЕТ СООБЩЕНИЕ!**\n\n**КАК УДАЛИТЬ ОДНО:**\n1️⃣ Ответь на сообщение → .del\n\n**КАК ЗАМУТИТЬ:**\n1️⃣ Ответь на сообщение → .mute\n2️⃣ Бот удалит сообщение и замутит человека!\n3️⃣ Все новые сообщения будут удаляться автоматически!", reply_markup=reply_markup, parse_mode="Markdown")

def admin_panel(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("⛔ Доступ запрещён!")
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("📝 Логи", callback_data="logs")],
        [InlineKeyboardButton("🚨 Варны", callback_data="warns_list")],
        [InlineKeyboardButton("💾 Сохранённое", callback_data="saved_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔐 **АДМИН-ПАНЕЛЬ**", reply_markup=reply_markup, parse_mode="Markdown")

# ============================================
# КНОПКИ
# ============================================
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "back_menu":
        keyboard = [
            [InlineKeyboardButton("🎮 Все команды", callback_data="all_commands")],
            [InlineKeyboardButton("💾 Сохранённое", callback_data="saved_list")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("🌟 **SMERTNYTEAM BOT V9.0**\n\n🔥 **.MUTE ТЕПЕРЬ УДАЛЯЕТ СООБЩЕНИЕ!**\n\n**КАК УДАЛИТЬ ОДНО:**\n1️⃣ Ответь на сообщение → .del\n\n**КАК ЗАМУТИТЬ:**\n1️⃣ Ответь на сообщение → .mute\n2️⃣ Бот удалит сообщение и замутит человека!\n3️⃣ Все новые сообщения будут удаляться автоматически!", reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "all_commands":
        keyboard = [
            [InlineKeyboardButton("🗑️ Удалить", callback_data="cmd_del"),
             InlineKeyboardButton("🔇 Мут", callback_data="cmd_mute")],
            [InlineKeyboardButton("🔊 Размут", callback_data="cmd_unmute"),
             InlineKeyboardButton("⚠️ Варн", callback_data="cmd_warn")],
            [InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist"),
             InlineKeyboardButton("💾 Сохранить", callback_data="cmd_save")],
            [InlineKeyboardButton("📂 Сохранённое", callback_data="saved_list"),
             InlineKeyboardButton("💬 Спам", callback_data="cmd_spam")],
            [InlineKeyboardButton("🎲 Монетка", callback_data="cmd_coin"),
             InlineKeyboardButton("🎯 Кубик", callback_data="cmd_dice")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("🎮 **ВСЕ КОМАНДЫ**\n\nВ ЛИЧКЕ (ответь на сообщение):\n.del — удалить одно\n.mute — удалить + автоудаление\n.unmute — отключить автоудаление\n.warn — выдать варн\n.save — сохранить\n\nБЕЗ ОТВЕТА:\n.spam .coin .dice .flip .quote", reply_markup=reply_markup, parse_mode="Markdown")
        return

    commands_info = {
        "cmd_del": "🗑️ **УДАЛИТЬ ОДНО**\nОтветь → .del",
        "cmd_mute": "🔇 **МУТ + УДАЛЕНИЕ**\nОтветь → .mute\nБот удалит сообщение и замутит человека!",
        "cmd_unmute": "🔊 **РАЗМУТ**\nОтветь → .unmute",
        "cmd_warn": "⚠️ **ВАРН**\nОтветь → .warn причина",
        "cmd_save": "💾 **СОХРАНИТЬ**\nОтветь на фото/файл → .save",
        "cmd_spam": "💬 **СПАМ**\n.spam 5 текст",
        "cmd_coin": "🎲 **МОНЕТКА**\n.coin",
        "cmd_dice": "🎯 **КУБИК**\n.dice"
    }
    if query.data in commands_info:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="all_commands")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(commands_info[query.data], reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "help":
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("❓ **ПОМОЩЬ**\n\n🔥 **УДАЛЕНИЕ РАБОТАЕТ!**\n\n📌 **.del** — удалить одно сообщение\n📌 **.mute** — удалить + автоудаление\n📌 **.unmute** — отключить автоудаление", reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "saved_list":
        user_id = query.from_user.id
        chat_id = query.message.chat.id
        c.execute("SELECT id, file_type, caption, date FROM saved WHERE chat_id=? OR user_id=? ORDER BY date DESC LIMIT 10", (chat_id, user_id))
        saved = c.fetchall()
        if not saved:
            keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text("📂 Сохранённых нет", reply_markup=reply_markup)
            return
        text = "📂 **Сохранённые:**\n\n"
        for item in saved:
            item_id, file_type, caption, date = item
            caption_preview = caption[:30] if caption else "(без текста)"
            text += f"• #{item_id} [{file_type}] {caption_preview}... ({date})\n"
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return

    if not is_admin(query.from_user.id):
        query.edit_message_text("⛔ Доступ запрещён!")
        return

    if query.data == "stats":
        c.execute("SELECT COUNT(*) FROM muted")
        muted_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM warns")
        warns_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        msgs_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM saved")
        saved_count = c.fetchone()[0]
        keyboard = [[InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(f"📊 **СТАТИСТИКА**\n\n🔇 В муте: {muted_count}\n⚠️ Варнов: {warns_count}\n💬 Сохранено: {msgs_count}\n💾 Файлов: {saved_count}", reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "admin_back":
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton("📝 Логи", callback_data="logs")],
            [InlineKeyboardButton("🚨 Варны", callback_data="warns_list")],
            [InlineKeyboardButton("💾 Сохранённое", callback_data="saved_list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("🔐 **АДМИН-ПАНЕЛЬ**", reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "mutelist":
        c.execute("SELECT user_id, until FROM muted LIMIT 10")
        muted = c.fetchall()
        if not muted:
            text = "📋 Список мута пуст"
        else:
            text = "📋 **ЗАМУЧЕННЫЕ:**\n\n"
            for uid, until in muted:
                try:
                    user = context.bot.get_chat(uid)
                    name = get_user_link(user)
                except:
                    name = f"ID:{uid}"
                until_text = f" до {until}" if until else " (навсегда)"
                text += f"• {name}{until_text}\n"
        keyboard = [[InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "settings":
        c.execute("SELECT value FROM settings WHERE key='max_warns'")
        max_warns = c.fetchone()[0]
        keyboard = [[InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(f"⚙️ **НАСТРОЙКИ**\n\nМакс. варнов до мута: {max_warns}", reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "logs":
        c.execute("SELECT user_id, text, date FROM messages ORDER BY date DESC LIMIT 10")
        logs = c.fetchall()
        if not logs:
            text = "📝 Логов нет"
        else:
            text = "📝 **ПОСЛЕДНИЕ 10 СООБЩЕНИЙ:**\n\n"
            for uid, msg_text, date in logs:
                try:
                    user = context.bot.get_chat(uid)
                    name = get_user_link(user)
                except:
                    name = f"ID:{uid}"
                text += f"• {name}: {msg_text[:30]}... ({date})\n"
        keyboard = [[InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return

    if query.data == "warns_list":
        c.execute("SELECT user_id, COUNT(*) FROM warns GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10")
        warns = c.fetchall()
        if not warns:
            text = "🚨 Варнов нет"
        else:
            text = "🚨 **ТОП ПО ВАРНАМ:**\n\n"
            for uid, count in warns:
                try:
                    user = context.bot.get_chat(uid)
                    name = get_user_link(user)
                except:
                    name = f"ID:{uid}"
                text += f"• {name}: {count} варнов\n"
        keyboard = [[InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return

# ============================================
# ОБРАБОТКА СООБЩЕНИЙ (АВТОУДАЛЕНИЕ!)
# ============================================
def handle_message(update: Update, context: CallbackContext):
    if not update.message:
        return

    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    text = update.message.text or ""

    if text.startswith('.'):
        parts = text.split()
        cmd = parts[0][1:]
        args = parts[1:]
        if cmd == "spam":
            context.args = args
            spam(update, context)
            return
        elif cmd == "coin":
            coin(update, context)
            return
        elif cmd == "dice":
            dice(update, context)
            return
        elif cmd == "flip":
            context.args = args
            flip(update, context)
            return
        elif cmd == "quote":
            quote(update, context)
            return
        elif cmd == "plove":
            context.args = args
            plove(update, context)
            return
        elif cmd == "spoiler":
            context.args = args
            spoiler(update, context)
            return
        elif cmd == "print":
            context.args = args
            print_cmd(update, context)
            return
        elif cmd == "joke":
            joke(update, context)
            return
        elif cmd == "leet":
            context.args = args
            leet(update, context)
            return
        elif cmd == "trol":
            context.args = args
            trol(update, context)
            return
        elif cmd == "agro":
            context.args = args
            agro(update, context)
            return
        elif cmd == "mutelist":
            mutelist(update, context)
            return
        elif cmd == "del":
            del_msg(update, context)
            return
        elif cmd == "mute":
            mute(update, context)
            return

    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, datetime('now'))", (update.message.message_id, chat_id, user_id, text or "[медиа]"))
    conn.commit()

    # АВТОУДАЛЕНИЕ ЗАМУЧЕННЫХ
    c.execute("SELECT until FROM muted WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    result = c.fetchone()
    if result:
        until = result[0]
        if until:
            if datetime.now() > datetime.strptime(until, "%Y-%m-%d %H:%M:%S"):
                c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, user_id))
                conn.commit()
                return
        try:
            update.message.delete()
            print(f"🗑️ АВТОУДАЛЕНИЕ: сообщение от {user_id}")
        except Exception as e:
            print(f"❌ Не удалось удалить: {e}")

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("🔄 ЗАПУСК...")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", main_menu))
    dp.add_handler(CommandHandler("menu", main_menu))
    dp.add_handler(CommandHandler("admin", admin_panel))

    dp.add_handler(CommandHandler("del", del_msg))
    dp.add_handler(CommandHandler("mute", mute))
    dp.add_handler(CommandHandler("unmute", unmute))
    dp.add_handler(CommandHandler("warn", warn))
    dp.add_handler(CommandHandler("mutelist", mutelist))
    dp.add_handler(CommandHandler("save", save_message))
    dp.add_handler(CommandHandler("saved", saved_list_cmd))
    dp.add_handler(CommandHandler("get", get_saved))
    dp.add_handler(CommandHandler("spam", spam))
    dp.add_handler(CommandHandler("coin", coin))
    dp.add_handler(CommandHandler("dice", dice))
    dp.add_handler(CommandHandler("flip", flip))
    dp.add_handler(CommandHandler("quote", quote))
    dp.add_handler(CommandHandler("plove", plove))
    dp.add_handler(CommandHandler("spoiler", spoiler))
    dp.add_handler(CommandHandler("print", print_cmd))
    dp.add_handler(CommandHandler("joke", joke))
    dp.add_handler(CommandHandler("leet", leet))
    dp.add_handler(CommandHandler("trol", trol))
    dp.add_handler(CommandHandler("agro", agro))

    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.all, handle_message))

    print("🚀 БОТ @Smertnyteam_bot ЗАПУЩЕН!")
    print("✅ .mute УДАЛЯЕТ СООБЩЕНИЕ + АВТОУДАЛЕНИЕ!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
