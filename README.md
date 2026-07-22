import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ===== ТОКЕН =====
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"

# ===== ЛОГИ =====
logging.basicConfig(level=logging.INFO)

# ===== СОЗДАЁМ БОТА =====
app = Application.builder().token(TOKEN).build()

# ===== КОМАНДА /start =====
async def start(update: Update, context):
    await update.message.reply_text(
        "✅ Бот работает!\n"
        "Отправь мне:\n"
        "- IP (например, 8.8.8.8)\n"
        "- Email\n"
        "- Любой текст"
    )

# ===== ОТВЕТ НА ЛЮБОЕ СООБЩЕНИЕ =====
async def echo(update: Update, context):
    text = update.message.text
    await update.message.reply_text(f"✅ Ты написал: {text}")

# ===== РЕГИСТРИРУЕМ КОМАНДЫ =====
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    app.run_polling()
