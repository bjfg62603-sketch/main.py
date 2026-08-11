import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГ ---
BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_ID = 8428048355  # Твой ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# --- БД ---
conn = sqlite3.connect("moderator.db", check_same_thread=False)
c = conn.cursor()

# Таблицы
c.execute("""CREATE TABLE IF NOT EXISTS muted (
    chat_id INTEGER, 
    user_id INTEGER, 
    until DATETIME,
    PRIMARY KEY (chat_id, user_id)
)""")

c.execute("""CREATE TABLE IF NOT EXISTS warns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    user_id INTEGER,
    reason TEXT,
    date DATETIME
)""")

c.execute("""CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER,
    chat_id INTEGER,
    user_id INTEGER,
    text TEXT,
    date DATETIME
)""")

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")

# Настройки по умолчанию
c.execute("INSERT OR IGNORE INTO settings VALUES ('max_warns', '5')")
c.execute("INSERT OR IGNORE INTO settings VALUES ('auto_delete', 'true')")
conn.commit()

# --- АДМИН-ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Доступ запрещён!")
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("📋 Мут-лист", callback_data="mutelist"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        InlineKeyboardButton("📝 Логи", callback_data="logs"),
        InlineKeyboardButton("🚨 Варны", callback_data="warns_list"),
        InlineKeyboardButton("💾 Бэкап БД", callback_data="backup")
    )
    
    await message.answer("🔐 **Админ-панель**\nВыбери действие:", 
                         reply_markup=keyboard, parse_mode="Markdown")

# --- ОБРАБОТКА КНОПОК АДМИНКИ ---
@dp.callback_query_handler(lambda c: c.data in ["stats", "mutelist", "settings", "logs", "warns_list", "backup"])
async def admin_callbacks(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⛔ Доступ запрещён!", show_alert=True)
    
    if callback.data == "stats":
        c.execute("SELECT COUNT(*) FROM muted")
        muted_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM warns")
        warns_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM messages")
        msgs_count = c.fetchone()[0]
        
        await callback.message.edit_text(
            f"📊 **Статистика**\n\n"
            f"🔇 В муте: {muted_count}\n"
            f"⚠️ Варнов выдано: {warns_count}\n"
            f"💬 Сохранено сообщений: {msgs_count}\n"
            f"👤 Админ: @DeIIIeted",
            parse_mode="Markdown"
        )
        await callback.answer()
    
    elif callback.data == "mutelist":
        c.execute("SELECT chat_id, user_id, until FROM muted")
        muted = c.fetchall()
        
        if not muted:
            text = "📋 **Список мута пуст**"
        else:
            text = "📋 **Замученные пользователи:**\n\n"
            for chat_id, user_id, until in muted[:10]:
                try:
                    user = await bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                
                until_text = f" до {until}" if until else " (навсегда)"
                text += f"• {name}{until_text}\n"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
        await callback.answer()
    
    elif callback.data == "settings":
        c.execute("SELECT value FROM settings WHERE key='max_warns'")
        max_warns = c.fetchone()[0]
        
        c.execute("SELECT value FROM settings WHERE key='auto_delete'")
        auto_delete = c.fetchone()[0]
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton(f"⚠️ Варны: {max_warns}", callback_data="set_warns"),
            InlineKeyboardButton(f"🗑️ Авто-удаление: {auto_delete}", callback_data="toggle_delete"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_admin")
        )
        
        await callback.message.edit_text(
            "⚙️ **Настройки**\n\n"
            f"Макс. варнов до мута: {max_warns}\n"
            f"Авто-удаление: {auto_delete}",
            reply_markup=keyboard, parse_mode="Markdown"
        )
        await callback.answer()
    
    elif callback.data == "logs":
        c.execute("SELECT user_id, text, date FROM messages ORDER BY date DESC LIMIT 10")
        logs = c.fetchall()
        
        if not logs:
            text = "📝 **Логов нет**"
        else:
            text = "📝 **Последние 10 сообщений:**\n\n"
            for user_id, msg_text, date in logs:
                try:
                    user = await bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {msg_text[:30]}... ({date})\n"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
        await callback.answer()
    
    elif callback.data == "warns_list":
        c.execute("SELECT user_id, COUNT(*) FROM warns GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 10")
        warns = c.fetchall()
        
        if not warns:
            text = "🚨 **Варнов нет**"
        else:
            text = "🚨 **Топ по варнам:**\n\n"
            for user_id, count in warns:
                try:
                    user = await bot.get_chat(user_id)
                    name = user.full_name or f"ID: {user_id}"
                except:
                    name = f"ID: {user_id}"
                text += f"• {name}: {count} варнов\n"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
        await callback.answer()
    
    elif callback.data == "backup":
        # Создаём бэкап БД
        with open("moderator.db", "rb") as f:
            await callback.message.answer_document(f, caption="💾 Бэкап базы данных")
        await callback.answer()

# --- КОМАНДЫ .mute .unmute .warn ---
@dp.message_handler(commands=['mute'])
async def mute_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение пользователя!")
    
    target = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    # Проверяем время (если указано)
    args = message.get_args()
    until = None
    if args:
        try:
            minutes = int(args.replace('m', ''))
            until = datetime.now() + timedelta(minutes=minutes)
            until = until.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    
    c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, ?)", (chat_id, target.id, until))
    conn.commit()
    
    await message.delete()
    await message.answer(f"🔇 {target.mention} замучен!" + (f" на {minutes} мин." if until else ""))

@dp.message_handler(commands=['unmute'])
async def unmute_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение пользователя!")
    
    target = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, target.id))
    conn.commit()
    
    await message.delete()
    await message.answer(f"🔊 {target.mention} размучен!")

@dp.message_handler(commands=['warn'])
async def warn_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение пользователя!")
    
    target = message.reply_to_message.from_user
    chat_id = message.chat.id
    reason = message.get_args() or "Без причины"
    
    c.execute("INSERT INTO warns (chat_id, user_id, reason, date) VALUES (?, ?, ?, datetime('now'))", 
              (chat_id, target.id, reason))
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM warns WHERE chat_id=? AND user_id=?", (chat_id, target.id))
    warns_count = c.fetchone()[0]
    
    c.execute("SELECT value FROM settings WHERE key='max_warns'")
    max_warns = int(c.fetchone()[0])
    
    await message.delete()
    
    if warns_count >= max_warns:
        c.execute("INSERT OR REPLACE INTO muted VALUES (?, ?, NULL)", (chat_id, target.id))
        conn.commit()
        await message.answer(f"🔇 {target.mention} автоматически замучен! ({warns_count} варнов)")
    else:
        await message.answer(f"⚠️ {target.mention} предупреждение {warns_count}/{max_warns}. Причина: {reason}")

# --- АВТОУДАЛЕНИЕ ---
@dp.message_handler()
async def filter_messages(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Сохраняем всё в лог
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, datetime('now'))",
              (message.message_id, chat_id, user_id, message.text or "[медиа]"))
    conn.commit()
    
    # Проверяем мут
    c.execute("SELECT until FROM muted WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    result = c.fetchone()
    
    if result:
        until = result[0]
        if until:
            # Проверяем, не истекло ли время
            if datetime.now() > datetime.strptime(until, "%Y-%m-%d %H:%M:%S"):
                c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, user_id))
                conn.commit()
                return
        
        # Удаляем сообщение
        try:
            await message.delete()
        except:
            pass

# --- НАЗАД В АДМИНКУ ---
@dp.callback_query_handler(lambda c: c.data == "back_admin")
async def back_admin(callback: types.CallbackQuery):
    await admin_panel(callback.message)

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("🤖 Бот @Smertnyteam_bot запущен!")
    print(f"👤 Админ: {ADMIN_ID}")
    executor.start_polling(dp)
