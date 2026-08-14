# bot.py
import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "8799739281:AAGeD8cWh2GKey6M-zXH-7q9yAsieZz0I_c"
ADMIN_ID = 8428048355

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("freeze"))
async def freeze(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("Нет")
    
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("/freeze @username 100")
    
    target = args[1].replace("@", "")
    count = int(args[2]) if len(args) > 2 else 100
    
    await message.reply(f"Начинаю {target}")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    success = 0
    
    for i in range(count):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={
                    "chat_id": target,
                    "text": f"Жалоба {i+1}",
                    "reply_to_message_id": random.randint(1, 9999)
                })
            success += 1
            await asyncio.sleep(0.5)
        except:
            pass
    
    await message.reply(f"✅ {success}/{count}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
