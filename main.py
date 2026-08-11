import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- КОНФИГ ---
BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_ID = 8428048355

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

# --- АДМИН-ПАНЕЛЬ ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Доступ запрещён!")
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("📝 Логи", callback_data="logs")],
        [InlineKeyboardButton("🚨 Варны", callback_data="warns_list")],
        [InlineKeyboardButton("💾 Бэкап БД", callback_data="backup")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🔐 **Админ-панель**\nВыбери действие:", reply_markup=reply_markup, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return await query.edit_message_text("⛔ Доступ запрещён!")
    
    if query.data == "stats":
        c.execute("SELECT COUNT(*) FROM muted")
        muted_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM warns")
        warns_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        msgs_count = c.fetchone()[0]
        
        await query.edit_message_text(
            f"📊 **Статистика**\n\n🔇 В муте: {muted_count}\n⚠️ Варнов: {warns_count}\n💬 Сохранено: {msgs_count}",
            parse_mode="Markdown"
        )
    
    elif query.data == "mutelist":
        c.execute("SELECT user_id, until FROM muted LIMIT 10")
        muted = c.fetchall()
        
        if not muted:
            text = "📋 Список мута пуст"
        else:
            text = "📋 **Замученные:**\n\n"
            for user_id, until in muted:
                try:
                    user = await context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                until_text = f" до {until}" if until else " (навсегда)"
                text += f"• {name}{until_text}\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif query.data == "settings":
        c.execute("SELECT value FROM settings WHERE key='max_warns'")
        max_warns = c.fetchone()[0]
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚙️ **Настройки**\n\nМакс. варнов до мута: {max_warns}",
            reply_markup=reply_markup, parse_mode="Markdown"
        )
    
    elif query.data == "logs":
        c.execute("SELECT user_id, text, date FROM messages ORDER BY date DESC LIMIT 10")
        logs = c.fetchall()
        
        if not logs:
            text = "📝 Логов нет"
        else:
            text = "📝 **Последние 10 сообщений:**\n\n"
            for user_id, msg_text, date in logs:
                try:
                    user = await context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {msg_text[:30]}... ({date})\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif query.data == "warns_list":
        c.execute("SELECT user_id, COUNT(*) FROM warns GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10")
        warns = c.fetchall()
        
        if not warns:
            text = "🚨 Варнов нет"
        else:
            text = "🚨 **Топ по варнам:**\n\n"
            for user_id, count in warns:
                try:
                    user = await context.bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {count} варнов\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif query.data == "backup":
        with open("moderator.db", "rb") as f:
            await query.message.reply_document(f, caption="💾 Бэкап базы данных")
    
    elif query.data == "back_admin":
        await admin_panel(update, context)

# --- КОМАНДЫ ---
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Ответь на сообщение!")
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    
    args = context.args
    until = None
    if args:
        try:
            minutes = int(args[0].replace('m', ''))
            until = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    
    c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, ?)", (chat_id, target.id, until))
    conn.commit()
    
    await update.message.delete()
    await update.message.reply_text(f"🔇 {target.mention_html()} замучен!" + (f" на {minutes} мин." if until else ""), parse_mode="HTML")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Ответь на сообщение!")
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    
    c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, target.id))
    conn.commit()
    
    await update.message.delete()
    await update.message.reply_text(f"🔊 {target.mention_html()} размучен!", parse_mode="HTML")

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Ответь на сообщение!")
    
    target = update.message.reply_to_message.from_user
    chat_id = update.message.chat.id
    reason = " ".join(context.args) or "Без причины"
    
    c.execute("INSERT INTO warns (chat_id, user_id, reason, date) VALUES (?, ?, ?, datetime('now'))", 
              (chat_id, target.id, reason))
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM warns WHERE chat_id=? AND user_id=?", (chat_id, target.id))
    warns_count = c.fetchone()[0]
    
    c.execute("SELECT value FROM settings WHERE key='max_warns'")
    max_warns = int(c.fetchone()[0])
    
    await update.message.delete()
    
    if warns_count >= max_warns:
        c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, NULL)", (chat_id, target.id))
        conn.commit()
        await update.message.reply_text(f"🔇 {target.mention_html()} автоматически замучен! ({warns_count} варнов)", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ {target.mention_html()} предупреждение {warns_count}/{max_warns}. Причина: {reason}", parse_mode="HTML")

# --- АВТОУДАЛЕНИЕ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    # Сохраняем в лог
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, datetime('now'))",
              (update.message.message_id, chat_id, user_id, update.message.text or "[медиа]"))
    conn.commit()
    
    # Проверяем мут
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
            await update.message.delete()
        except:
            pass

# --- ЗАПУСК ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("🤖 Бот @Smertnyteam_bot запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
