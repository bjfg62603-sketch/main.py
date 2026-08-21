import os

BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")  # получи у @BotFather
ADMIN_IDS = [8428048355, 8164031956]  # @oryke и @shezik
BASE_URL = os.getenv("RENDER_URL")  # или захардкодь: "https://твой-бот.onrender.com"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
