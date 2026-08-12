import os
import sqlite3
import random
import time
import shutil
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

# --- КОНФИГ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8428048355))

print("🚀 Бот запускается...")

# --- БД ---
conn = sqlite3.connect("moderator.db", check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS muted (
    chat_id INTEGER, 
    user_id INTEGER, 
    until TEXT,
    PRIMARY KEY (chat_id, user_id)
)""")

c.execute("""CREATE TABLE IF NOT EXISTS warns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    user_id INTEGER,
    reason TEXT,
    date TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER,
    chat_id INTEGER,
    user_id INTEGER,
    text TEXT,
    date TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS saved (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    user_id INTEGER,
    file_id TEXT,
    file_type TEXT,
    caption TEXT,
    date TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")

c.execute("INSERT OR IGNORE INTO settings VALUES ('max_warns', '5')")
c.execute("INSERT OR IGNORE INTO settings VALUES ('auto_save', 'false')")
conn.commit()

print("✅ База данных готова")

# --- СОЗДАЁМ ПАПКУ ДЛЯ ФАЙЛОВ ---
if not os.path.exists("saved_files"):
    os.makedirs("saved_files")

# --- ПОИСК ПОЛЬЗОВАТЕЛЯ ---
def find_user_by_username(context, username):
    try:
        return context.bot.get_chat(username)
    except:
        return None

def is_admin(user_id):
    return user_id == ADMIN_ID

# ============================================
# ГЛАВНОЕ МЕНЮ
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
    
    update.message.reply_text(
        "🌟 **SmertnyTeam Bot**\n\n"
        "Быстрая автоматизация чатов.\n"
        "Команды:\n"
        "• `.save` — сохранить сообщение/файл\n"
        "• `.saved` — список сохранённого\n"
        "• `.mute @user` — замутить",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ============================================
# ВСЕ КОМАНДЫ
# ============================================

def all_commands(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🔇 Мут", callback_data="cmd_mute"),
         InlineKeyboardButton("🔊 Размут", callback_data="cmd_unmute")],
        [InlineKeyboardButton("⚠️ Варн", callback_data="cmd_warn"),
         InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist")],
        [InlineKeyboardButton("💾 Сохранить", callback_data="cmd_save"),
         InlineKeyboardButton("📂 Сохранённое", callback_data="saved_list")],
        [InlineKeyboardButton("💬 Спам", callback_data="cmd_spam"),
         InlineKeyboardButton("🎲 Монетка", callback_data="cmd_coin")],
        [InlineKeyboardButton("📝 Цитата", callback_data="cmd_quote"),
         InlineKeyboardButton("🔄 Переворот", callback_data="cmd_flip")],
        [InlineKeyboardButton("🎯 Кубик", callback_data="cmd_dice"),
         InlineKeyboardButton("✏️ Печать", callback_data="cmd_print")],
        [InlineKeyboardButton("❤️ Сердечки", callback_data="cmd_plove"),
         InlineKeyboardButton("😴 Спойлер", callback_data="cmd_spoiler")],
        [InlineKeyboardButton("🎭 Троллинг", callback_data="cmd_trol"),
         InlineKeyboardButton("🔊 Агро-режим", callback_data="cmd_agro")],
        [InlineKeyboardButton("🧠 Сверхразум", callback_data="cmd_leet"),
         InlineKeyboardButton("📝 Анекдот", callback_data="cmd_joke")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "🎮 **Все команды SmertnyTeam**\n\n"
        "Выберите команду для информации:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ============================================
# .SAVE — СОХРАНЕНИЕ СООБЩЕНИЙ И ФАЙЛОВ
# ============================================

def save_message(update: Update, context: CallbackContext):
    """Сохраняет сообщение, фото, видео, файлы"""
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение, которое хочешь сохранить!")
        return
    
    reply = update.message.reply_to_message
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    file_id = None
    file_type = "text"
    caption = reply.caption or ""
    text = reply.text or ""
    
    # Определяем тип контента и сохраняем
    if reply.photo:
        file_id = reply.photo[-1].file_id
        file_type = "photo"
        caption = reply.caption or ""
        # Скачиваем фото
        file = context.bot.get_file(file_id)
        file.download(f"saved_files/photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
    elif reply.video:
        file_id = reply.video.file_id
        file_type = "video"
        caption = reply.caption or ""
        file = context.bot.get_file(file_id)
        file.download(f"saved_files/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    elif reply.document:
        file_id = reply.document.file_id
        file_type = "document"
        caption = reply.caption or ""
        file = context.bot.get_file(file_id)
        file.download(f"saved_files/doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{reply.document.file_name}")
    elif reply.voice:
        file_id = reply.voice.file_id
        file_type = "voice"
        file = context.bot.get_file(file_id)
        file.download(f"saved_files/voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg")
    elif reply.text:
        file_id = None
        file_type = "text"
        text = reply.text or ""
    else:
        update.message.reply_text("❌ Этот тип сообщения пока нельзя сохранить!")
        return
    
    # Сохраняем в БД
    c.execute("""INSERT INTO saved (chat_id, user_id, file_id, file_type, caption, date) 
                 VALUES (?, ?, ?, ?, ?, datetime('now'))""",
              (chat_id, user_id, file_id, file_type, caption or text))
    conn.commit()
    
    update.message.reply_text(
        f"💾 **Сохранено!**\n"
        f"Тип: {file_type}\n"
        f"ID: {c.lastrowid}",
        parse_mode="Markdown"
    )
    
    # Удаляем команду .save
    try:
        update.message.delete()
    except:
        pass

# ============================================
# .SAVED — СПИСОК СОХРАНЁННОГО
# ============================================

def saved_list_cmd(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    c.execute("SELECT id, file_type, caption, date FROM saved WHERE chat_id=? OR user_id=? ORDER BY date DESC LIMIT 10",
              (chat_id, user_id))
    saved = c.fetchall()
    
    if not saved:
        update.message.reply_text("📂 У тебя пока нет сохранённых сообщений!")
        return
    
    text = "📂 **Сохранённые сообщения:**\n\n"
    for item in saved:
        item_id, file_type, caption, date = item
        caption_preview = caption[:30] if caption else "(без текста)"
        text += f"• #{item_id} [{file_type}] {caption_preview}... ({date})\n"
    
    text += "\n📌 Чтобы посмотреть сохранённое, используй `.get 1`"
    update.message.reply_text(text, parse_mode="Markdown")

# ============================================
# .GET — ПОЛУЧИТЬ СОХРАНЁННОЕ ПО ID
# ============================================

def get_saved(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.get 1` (где 1 — ID сохранённого)")
        return
    
    try:
        item_id = int(args[0])
        c.execute("SELECT file_id, file_type, caption FROM saved WHERE id=?", (item_id,))
        result = c.fetchone()
        
        if not result:
            update.message.reply_text(f"❌ Сохранённое с ID {item_id} не найдено!")
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
            update.message.reply_text(f"📝 Сохранённый текст:\n\n{caption}")
        else:
            update.message.reply_text(f"Неизвестный тип: {file_type}")
    except:
        update.message.reply_text("❌ Ошибка! Используй: `.get 1`")

# ============================================
# ВСЕ КОМАНДЫ USEFLOW+
# ============================================

# --- .MUTE ---
def mute(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    
    if chat_id == user_id:
        args = context.args
        if not args:
            update.message.reply_text("❌ Использование: `.mute @username`")
            return
        
        username = args[0].replace('@', '')
        target = find_user_by_username(context, username)
        if not target:
            update.message.reply_text(f"❌ Пользователь @{username} не найден!")
            return
        
        target_id = target.id
        until = None
        minutes = 0
        if len(args) > 1:
            try:
                minutes = int(args[1].replace('m', ''))
                until = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, ?)", (user_id, target_id, until))
        conn.commit()
        
        mute_text = f"🔇 @{username} замучен!"
        if until:
            mute_text += f" на {minutes} мин."
        update.message.reply_text(mute_text)
        return
    
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение пользователя!")
        return
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    
    if target.id == user_id:
        update.message.reply_text("❌ Нельзя замутить себя!")
        return
    
    if is_admin(target.id):
        update.message.reply_text("❌ Нельзя замутить админа!")
        return
    
    until = None
    minutes = 0
    args = context.args
    if args:
        try:
            minutes = int(args[0].replace('m', ''))
            until = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    
    c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, ?)", (chat_id, target.id, until))
    conn.commit()
    
    try:
        update.message.delete()
    except:
        pass
    
    mute_text = f"🔇 {target.mention_html()} замучен!"
    if until:
        mute_text += f" на {minutes} мин."
    update.message.reply_text(mute_text, parse_mode="HTML")

# --- .UNMUTE ---
def unmute(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    
    if chat_id == user_id:
        args = context.args
        if not args:
            update.message.reply_text("❌ Использование: `.unmute @username`")
            return
        
        username = args[0].replace('@', '')
        target = find_user_by_username(context, username)
        if not target:
            update.message.reply_text(f"❌ Пользователь @{username} не найден!")
            return
        
        target_id = target.id
        c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (user_id, target_id))
        conn.commit()
        update.message.reply_text(f"🔊 @{username} размучен!")
        return
    
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение пользователя!")
        return
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    
    c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, target.id))
    conn.commit()
    
    try:
        update.message.delete()
    except:
        pass
    
    update.message.reply_text(f"🔊 {target.mention_html()} размучен!", parse_mode="HTML")

# --- .WARN ---
def warn(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    
    if chat_id == user_id:
        args = context.args
        if not args:
            update.message.reply_text("❌ Использование: `.warn @username`")
            return
        
        username = args[0].replace('@', '')
        target = find_user_by_username(context, username)
        if not target:
            update.message.reply_text(f"❌ Пользователь @{username} не найден!")
            return
        
        target_id = target.id
        reason = " ".join(args[1:]) or "Без причины"
        
        c.execute("INSERT INTO warns (chat_id, user_id, reason, date) VALUES (?, ?, ?, datetime('now'))", 
                  (user_id, target_id, reason))
        conn.commit()
        
        c.execute("SELECT COUNT(*) FROM warns WHERE chat_id=? AND user_id=?", (user_id, target_id))
        warns_count = c.fetchone()[0]
        
        c.execute("SELECT value FROM settings WHERE key='max_warns'")
        max_warns = int(c.fetchone()[0])
        
        if warns_count >= max_warns:
            c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, NULL)", (user_id, target_id))
            conn.commit()
            update.message.reply_text(f"🔇 @{username} авто-мут ({warns_count} варнов)")
        else:
            update.message.reply_text(f"⚠️ @{username} варн {warns_count}/{max_warns}. Причина: {reason}")
        return
    
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение пользователя!")
        return
    
    target = update.message.reply_to_message.from_user
    reason = " ".join(context.args) or "Без причины"
    
    c.execute("INSERT INTO warns (chat_id, user_id, reason, date) VALUES (?, ?, ?, datetime('now'))", 
              (chat_id, target.id, reason))
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM warns WHERE chat_id=? AND user_id=?", (chat_id, target.id))
    warns_count = c.fetchone()[0]
    
    c.execute("SELECT value FROM settings WHERE key='max_warns'")
    max_warns = int(c.fetchone()[0])
    
    try:
        update.message.delete()
    except:
        pass
    
    if warns_count >= max_warns:
        c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, NULL)", (chat_id, target.id))
        conn.commit()
        update.message.reply_text(f"🔇 {target.mention_html()} авто-мут ({warns_count} варнов)", parse_mode="HTML")
    else:
        update.message.reply_text(f"⚠️ {target.mention_html()} варн {warns_count}/{max_warns}. Причина: {reason}", parse_mode="HTML")

# --- .MUTELIST ---
def mutelist(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    
    c.execute("SELECT user_id, until FROM muted WHERE chat_id=?", (chat_id,))
    muted = c.fetchall()
    
    if not muted:
        update.message.reply_text("📋 В этом чате нет замученных")
        return
    
    text = "📋 **Замученные:**\n\n"
    for user_id, until in muted:
        try:
            user = context.bot.get_chat(user_id)
            name = user.full_name or f"ID: {user_id}"
        except:
            name = f"ID: {user_id}"
        until_text = f" до {until}" if until else " (навсегда)"
        text += f"• {name}{until_text}\n"
    
    update.message.reply_text(text, parse_mode="Markdown")

# --- .SPAM ---
def spam(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("❌ Использование: `.spam 5 текст`")
        return
    
    try:
        count = int(args[0])
        if count > 20:
            count = 20
            update.message.reply_text("⚠️ Максимум 20 сообщений")
        text = " ".join(args[1:])
        
        try:
            update.message.delete()
        except:
            pass
        
        for _ in range(count):
            update.message.reply_text(text)
    except:
        update.message.reply_text("❌ Ошибка! Используй: `.spam 5 текст`")

# --- .COIN ---
def coin(update: Update, context: CallbackContext):
    result = random.choice(["🦅 Орёл", "🪙 Решка"])
    update.message.reply_text(f"🎲 {result}!")

# --- .DICE ---
def dice(update: Update, context: CallbackContext):
    result = random.randint(1, 6)
    emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    update.message.reply_text(f"🎲 {emojis[result-1]} {result}!")

# --- .FLIP ---
def flip(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.flip текст`")
        return
    
    text = " ".join(args)
    flipped = text[::-1]
    update.message.reply_text(f"🔄 {flipped}")

# --- .QUOTE ---
def quote(update: Update, context: CallbackContext):
    quotes = [
        "💭 Жизнь — это то, что происходит, пока ты строишь планы.",
        "💭 Будь собой, все остальные роли уже заняты.",
        "💭 Успех — это умение двигаться от неудачи к неудаче.",
        "💭 Лучший способ предсказать будущее — создать его.",
        "💭 Только тот, кто рискует, может быть свободным."
    ]
    update.message.reply_text(random.choice(quotes))

# --- .PLOVE ---
def plove(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        count = 5
    else:
        try:
            count = int(args[0])
            if count > 20:
                count = 20
        except:
            count = 5
    
    hearts = "❤️" * count
    update.message.reply_text(f"{hearts}")

# --- .SPOILER ---
def spoiler(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.spoiler текст`")
        return
    
    text = " ".join(args)
    update.message.reply_text(f"||{text}||", parse_mode="MarkdownV2")

# --- .PRINT ---
def print_cmd(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.print текст`")
        return
    
    text = " ".join(args)
    try:
        update.message.delete()
    except:
        pass
    update.message.reply_text(text)

# --- .JOKE ---
def joke(update: Update, context: CallbackContext):
    jokes = [
        "😂 Встречаются два программиста: — У тебя есть 5 рублей? — Да. — А у меня есть 10. Давай скинемся по 5 и купим пиццу?",
        "😂 — Почему программисты не любят природу? — Слишком много багов.",
        "😂 — Что сказал один бит другому? — Мне тебя не хватает.",
        "😂 Как отличить бота от человека? Бот ответит сразу, человек — через 5 минут с извинениями."
    ]
    update.message.reply_text(random.choice(jokes))

# --- .LEET ---
def leet(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.leet текст`")
        return
    
    text = " ".join(args)
    leet_map = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7', 'b': '8', 'g': '9'}
    result = ''.join(leet_map.get(c.lower(), c) if c.isalpha() else c for c in text)
    update.message.reply_text(f"🧠 {result}")

# --- .TROL ---
def trol(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.trol текст`")
        return
    
    text = " ".join(args)
    result = text.swapcase()
    update.message.reply_text(f"🎭 {result}")

# --- .AGRO ---
def agro(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("❌ Использование: `.agro текст`")
        return
    
    text = " ".join(args)
    result = text.upper() + "!!1"
    update.message.reply_text(f"🔊 {result}")

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

def admin_panel(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
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
    update.message.reply_text("🔐 **Админ-панель**", reply_markup=reply_markup, parse_mode="Markdown")

# ============================================
# ОБРАБОТКА КНОПОК
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
        query.edit_message_text(
            "🌟 **SmertnyTeam Bot**\n\n"
            "Быстрая автоматизация чатов.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    if query.data == "all_commands":
        keyboard = [
            [InlineKeyboardButton("🔇 Мут", callback_data="cmd_mute"),
             InlineKeyboardButton("🔊 Размут", callback_data="cmd_unmute")],
            [InlineKeyboardButton("⚠️ Варн", callback_data="cmd_warn"),
             InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist")],
            [InlineKeyboardButton("💾 Сохранить", callback_data="cmd_save"),
             InlineKeyboardButton("📂 Сохранённое", callback_data="saved_list")],
            [InlineKeyboardButton("💬 Спам", callback_data="cmd_spam"),
             InlineKeyboardButton("🎲 Монетка", callback_data="cmd_coin")],
            [InlineKeyboardButton("📝 Цитата", callback_data="cmd_quote"),
             InlineKeyboardButton("🔄 Переворот", callback_data="cmd_flip")],
            [InlineKeyboardButton("🎯 Кубик", callback_data="cmd_dice"),
             InlineKeyboardButton("✏️ Печать", callback_data="cmd_print")],
            [InlineKeyboardButton("❤️ Сердечки", callback_data="cmd_plove"),
             InlineKeyboardButton("😴 Спойлер", callback_data="cmd_spoiler")],
            [InlineKeyboardButton("🎭 Троллинг", callback_data="cmd_trol"),
             InlineKeyboardButton("🔊 Агро-режим", callback_data="cmd_agro")],
            [InlineKeyboardButton("🧠 Сверхразум", callback_data="cmd_leet"),
             InlineKeyboardButton("📝 Анекдот", callback_data="cmd_joke")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "🎮 **Все команды SmertnyTeam**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    # Информация о командах
    commands_info = {
        "cmd_mute": "🔇 **Мут**\n\nВ ЛС: `.mute @username`\nВ группе: ответь + `.mute`",
        "cmd_unmute": "🔊 **Размут**\n\nВ ЛС: `.unmute @username`\nВ группе: ответь + `.unmute`",
        "cmd_warn": "⚠️ **Варн**\n\n`.warn @username причина`\nПосле 5 варнов — авто-мут",
        "cmd_save": "💾 **Сохранить**\n\nОтветь на сообщение + `.save`\nСохраняет фото, видео, файлы, текст",
        "cmd_spam": "💬 **Спам**\n\n`.spam 5 текст` (макс 20)",
        "cmd_coin": "🎲 **Монетка**\n\n`.coin`",
        "cmd_quote": "📝 **Цитата**\n\n`.quote`",
        "cmd_flip": "🔄 **Переворот**\n\n`.flip текст`",
        "cmd_dice": "🎯 **Кубик**\n\n`.dice`",
        "cmd_print": "✏️ **Печать**\n\n`.print текст`",
        "cmd_plove": "❤️ **Сердечки**\n\n`.plove` или `.plove 10`",
        "cmd_spoiler": "😴 **Спойлер**\n\n`.spoiler текст`",
        "cmd_trol": "🎭 **Троллинг**\n\n`.trol текст`",
        "cmd_agro": "🔊 **Агро-режим**\n\n`.agro текст`",
        "cmd_leet": "🧠 **Сверхразум**\n\n`.leet текст`",
        "cmd_joke": "📝 **Анекдот**\n\n`.joke`"
    }
    
    if query.data in commands_info:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="all_commands")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            commands_info[query.data],
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    if query.data == "help":
        query.edit_message_text(
            "❓ **Помощь**\n\n"
            "📌 Основные команды:\n"
            "`.save` — сохранить сообщение\n"
            "`.saved` — список сохранённого\n"
            "`.get 1` — получить по ID\n"
            "`.mute @user` — замутить\n"
            "`.unmute @user` — размутить\n"
            "`.warn @user` — выдать варн\n"
            "`.spam 5 текст` — спам\n"
            "`.coin` .dice .flip .quote\n"
            "`.trol` .agro .leet .joke",
            parse_mode="Markdown"
        )
        return
    
    if query.data == "saved_list":
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        
        c.execute("SELECT id, file_type, caption, date FROM saved WHERE chat_id=? OR user_id=? ORDER BY date DESC LIMIT 10",
                  (chat_id, user_id))
        saved = c.fetchall()
        
        if not saved:
            query.edit_message_text("📂 У тебя пока нет сохранённых сообщений!")
            return
        
        text = "📂 **Сохранённые сообщения:**\n\n"
        for item in saved:
            item_id, file_type, caption, date = item
            caption_preview = caption[:30] if caption else "(без текста)"
            text += f"• #{item_id} [{file_type}] {caption_preview}... ({date})\n"
        
        text += "\n📌 `.get 1` — получить по ID"
        query.edit_message_text(text, parse_mode="Markdown")
        return
    
    # Статистика для админа
    if query.from_user.id != ADMIN_ID:
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
        
        query.edit_message_text(
            f"📊 **Статистика**\n\n"
            f"🔇 В муте: {muted_count}\n"
            f"⚠️ Варнов: {warns_count}\n"
            f"💬 Сохранено: {msgs_count}\n"
            f"💾 Сохранённых файлов: {saved_count}",
            parse_mode="Markdown"
        )
        return
    
    if query.data == "mutelist":
        c.execute("SELECT user_id, until FROM muted LIMIT 10")
        muted = c.fetchall()
        
        if not muted:
            text = "📋 Список мута пуст"
        else:
            text = "📋 **Замученные:**\n\n"
            for user_id, until in muted:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                until_text = f" до {until}" if until else " (навсегда)"
                text += f"• {name}{until_text}\n"
        
        query.edit_message_text(text, parse_mode="Markdown")
        return
    
    if query.data == "settings":
        c.execute("SELECT value FROM settings WHERE key='max_warns'")
        max_warns = c.fetchone()[0]
        query.edit_message_text(f"⚙️ **Настройки**\n\nМакс. варнов до мута: {max_warns}", parse_mode="Markdown")
        return
    
    if query.data == "logs":
        c.execute("SELECT user_id, text, date FROM messages ORDER BY date DESC LIMIT 10")
        logs = c.fetchall()
        
        if not logs:
            text = "📝 Логов нет"
        else:
            text = "📝 **Последние 10 сообщений:**\n\n"
            for user_id, msg_text, date in logs:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {msg_text[:30]}... ({date})\n"
        
        query.edit_message_text(text, parse_mode="Markdown")
        return
    
    if query.data == "warns_list":
        c.execute("SELECT user_id, COUNT(*) FROM warns GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10")
        warns = c.fetchall()
        
        if not warns:
            text = "🚨 Варнов нет"
        else:
            text = "🚨 **Топ по варнам:**\n\n"
            for user_id, count in warns:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {count} варнов\n"
        
        query.edit_message_text(text, parse_mode="Markdown")
        return

# --- ОБРАБОТКА СООБЩЕНИЙ ---
def handle_message(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, datetime('now'))",
              (update.message.message_id, chat_id, user_id, update.message.text or "[медиа]"))
    conn.commit()
    
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
        except:
            pass

# ============================================
# ЗАПУСК
# ============================================

def main():
    print("🔄 Создаём приложение...")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Главные
    dp.add_handler(CommandHandler("start", main_menu))
    dp.add_handler(CommandHandler("menu", main_menu))
    dp.add_handler(CommandHandler("admin", admin_panel))
    
    # Сохранение
    dp.add_handler(CommandHandler("save", save_message))
    dp.add_handler(CommandHandler("saved", saved_list_cmd))
    dp.add_handler(CommandHandler("get", get_saved))
    
    # Все команды
    dp.add_handler(CommandHandler("mute", mute))
    dp.add_handler(CommandHandler("unmute", unmute))
    dp.add_handler(CommandHandler("warn", warn))
    dp.add_handler(CommandHandler("mutelist", mutelist))
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
    
    print("🚀 Бот @Smertnyteam_bot запущен!")
    print("✅ Добавлены команды: .save, .saved, .get")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
