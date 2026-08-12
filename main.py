import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

# --- КОНФИГ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8428048355))

print("🚀 Бот запускается...")
print(f"✅ Токен загружен: {BOT_TOKEN[:10]}...")
print(f"✅ Админ: {ADMIN_ID}")

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

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")

c.execute("INSERT OR IGNORE INTO settings VALUES ('max_warns', '5')")
conn.commit()

print("✅ База данных готова")

# --- ПРОВЕРКА АДМИНА ---
def is_admin(user_id):
    return user_id == ADMIN_ID

# --- КОМАНДЫ (РАБОТАЮТ В ЛЮБОМ ЧАТЕ) ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text("✅ Бот работает! Используй /admin для управления")

def admin_panel(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("⛔ Доступ запрещён!")
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("📝 Логи", callback_data="logs")],
        [InlineKeyboardButton("🚨 Варны", callback_data="warns_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔐 **Админ-панель**", reply_markup=reply_markup, parse_mode="Markdown")

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
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
        
        query.edit_message_text(
            f"📊 Статистика\n\n🔇 В муте: {muted_count}\n⚠️ Варнов: {warns_count}\n💬 Сохранено: {msgs_count}"
        )
    
    elif query.data == "mutelist":
        c.execute("SELECT user_id, until FROM muted LIMIT 10")
        muted = c.fetchall()
        
        if not muted:
            text = "📋 Список мута пуст"
        else:
            text = "📋 Замученные:\n\n"
            for user_id, until in muted:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                until_text = f" до {until}" if until else " (навсегда)"
                text += f"• {name}{until_text}\n"
        
        query.edit_message_text(text)
    
    elif query.data == "settings":
        c.execute("SELECT value FROM settings WHERE key='max_warns'")
        max_warns = c.fetchone()[0]
        query.edit_message_text(f"⚙️ Настройки\n\nМакс. варнов до мута: {max_warns}")
    
    elif query.data == "logs":
        c.execute("SELECT user_id, text, date FROM messages ORDER BY date DESC LIMIT 10")
        logs = c.fetchall()
        
        if not logs:
            text = "📝 Логов нет"
        else:
            text = "📝 Последние 10 сообщений:\n\n"
            for user_id, msg_text, date in logs:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {msg_text[:30]}... ({date})\n"
        
        query.edit_message_text(text)
    
    elif query.data == "warns_list":
        c.execute("SELECT user_id, COUNT(*) FROM warns GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10")
        warns = c.fetchall()
        
        if not warns:
            text = "🚨 Варнов нет"
        else:
            text = "🚨 Топ по варнам:\n\n"
            for user_id, count in warns:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {count} варнов\n"
        
        query.edit_message_text(text)

# --- КОМАНДЫ ДЛЯ ЧАТОВ (РЕЖИМ СЕКРЕТАРЯ) ---
def mute(update: Update, context: CallbackContext):
    """Мутит пользователя в любом чате (ответь на сообщение + .mute)"""
    
    # Проверяем, есть ли ответ на сообщение
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение пользователя, которого хочешь замутить!")
        return
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    
    # Не даём замутить самого себя
    if target.id == update.effective_user.id:
        update.message.reply_text("❌ Нельзя замутить себя!")
        return
    
    # Не даём замутить админа
    if is_admin(target.id):
        update.message.reply_text("❌ Нельзя замутить админа!")
        return
    
    # Проверяем время мута
    args = context.args
    until = None
    minutes = 0
    if args:
        try:
            minutes = int(args[0].replace('m', ''))
            until = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    
    # Добавляем в мут-лист
    c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, ?)", (chat_id, target.id, until))
    conn.commit()
    
    # Удаляем команду .mute
    try:
        update.message.delete()
    except:
        pass
    
    # Отправляем уведомление от бота
    mute_text = f"🔇 {target.mention_html()} замучен!"
    if until:
        mute_text += f" на {minutes} мин."
    update.message.reply_text(mute_text, parse_mode="HTML")

def unmute(update: Update, context: CallbackContext):
    """Размучивает пользователя в любом чате"""
    
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение пользователя, которого хочешь размутить!")
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

def warn(update: Update, context: CallbackContext):
    """Выдаёт предупреждение пользователю"""
    
    if not update.message.reply_to_message:
        update.message.reply_text("❌ Ответь на сообщение пользователя!")
        return
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    
    if target.id == update.effective_user.id:
        update.message.reply_text("❌ Нельзя выдать варн себе!")
        return
    
    if is_admin(target.id):
        update.message.reply_text("❌ Нельзя выдать варн админу!")
        return
    
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

def mutelist(update: Update, context: CallbackContext):
    """Показывает список замученных в этом чате"""
    chat_id = update.message.chat.id
    
    c.execute("SELECT user_id, until FROM muted WHERE chat_id=?", (chat_id,))
    muted = c.fetchall()
    
    if not muted:
        update.message.reply_text("📋 В этом чате нет замученных")
        return
    
    text = "📋 **Замученные в этом чате:**\n\n"
    for user_id, until in muted:
        try:
            user = context.bot.get_chat(user_id)
            name = user.full_name or f"ID: {user_id}"
        except:
            name = f"ID: {user_id}"
        until_text = f" до {until}" if until else " (навсегда)"
        text += f"• {name}{until_text}\n"
    
    update.message.reply_text(text, parse_mode="Markdown")

# --- ОБРАБОТКА ВСЕХ СООБЩЕНИЙ ---
def handle_message(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    # Сохраняем сообщение в лог
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, datetime('now'))",
              (update.message.message_id, chat_id, user_id, update.message.text or "[медиа]"))
    conn.commit()
    
    # Проверяем, замучен ли пользователь
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

# --- ЗАПУСК ---
def main():
    print("🔄 Создаём приложение...")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Команды для админа
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    
    # Команды для всех чатов (режим секретаря)
    dp.add_handler(CommandHandler("mute", mute))
    dp.add_handler(CommandHandler("unmute", unmute))
    dp.add_handler(CommandHandler("warn", warn))
    dp.add_handler(CommandHandler("mutelist", mutelist))
    
    # Обработчики
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.all, handle_message))
    
    print("🚀 Бот @Smertnyteam_bot запущен!")
    print("✅ Режим секретаря включён!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
