import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ===== ТВОЙ ТОКЕН =====
TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"

# ===== ЛОГИ =====
logging.basicConfig(level=logging.INFO)

# ===== СОЗДАЁМ ПРИЛОЖЕНИЕ =====
app = Application.builder().token(TOKEN).build()

# ===== КОМАНДА /start =====
async def start(update, context):
    await update.message.reply_text("✅ Бот работает! Отправь мне текст, IP или email.")

# ===== ОТВЕТ НА ЛЮБОЕ СООБЩЕНИЕ =====
async def echo(update, context):
    await update.message.reply_text(f"✅ Ты написал: {update.message.text}")

# ===== РЕГИСТРИРУЕМ ОБРАБОТЧИКИ =====
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    app.run_polling()
