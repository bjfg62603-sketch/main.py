import os

BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")  # получи у @BotFather
ADMIN_IDS = [8428048355]  # твой ID (@oryke)
BASE_URL = os.getenv("RENDER_URL")  # например https://plutonium-bot.onrender.com
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
