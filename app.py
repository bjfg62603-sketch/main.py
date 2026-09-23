import asyncio
import logging
import random
import threading
from datetime import datetime
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.enums import ParseMode
from config import BOT_TOKEN, ADMIN_ID, CHANNELS
from database import (
    init_db, get_user, add_user, update_premium,
    spend_refs, get_all_users, get_stats
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== FLASK ДЛЯ RENDER ==========
flask_app = Flask(__name__)


@flask_app.route('/')
def home():
    return "Bot is alive!"


def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)


# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def check_subscription(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True


# ========== ГЕНЕРАЦИЯ ЦЕНЫ ==========
def generate_price(username, is_similar_to_word):
    base = random.randint(10, 30)
    if is_similar_to_word:
        base += 40
    if len(username) == 5:
        base += 20
    elif len(username) == 6:
        base += 10
    return f"${base} - ${base + random.randint(10, 20)}"


# ========== ПОИСК ЮЗЕРНЕЙМА (ИМИТАЦИЯ) ==========
async def search_username(length):
    """
    ИМИТАЦИЯ. Для реального поиска нужен юзер-бот (Telethon/Pyrogram).
    """
    for _ in range(10):
        username = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=length))
        if random.random() < 0.3:
            is_similar = any(c in "aeiou" for c in username.lower())
            return {
                "username": f"@{username}",
                "readability": f"{random.randint(5, 10)}/10",
                "price": generate_price(username, is_similar),
                "liquidity": f"{random.randint(4, 10)}/10",
                "status": "Свободен ⚡️"
            }
    return None


# ========== КЛАВИАТУРЫ ==========
def main_menu_kb():
    kb = [
        [KeyboardButton(text="🔍 Поиск юзернейма")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💎 Премиум")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def search_menu_kb():
    kb = [
        [InlineKeyboardButton(text="🔥 5 букв", callback_data="search_5"),
         InlineKeyboardButton(text="🔍 6 букв", callback_data="search_6")],
        [InlineKeyboardButton(text="🔒 Фильтр", callback_data="premium_filter"),
         InlineKeyboardButton(text="🔒 Ловушка", callback_data="premium_trap")],
        [InlineKeyboardButton(text="🔒 Похожие на слово", callback_data="premium_word")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ========== ХЕНДЛЕРЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    await add_user(
        message.from_user.id,
        username=message.from_user.username,
        referrer_id=referrer_id
    )

    if not await check_subscription(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Канал 1", url="https://t.me/adeptersmertnogo")],
            [InlineKeyboardButton(text="📢 Канал 2", url="https://t.me/smertnyteam")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
        ])
        await message.answer(
            "⚠️ Для использования бота подпишись на наши каналы:",
            reply_markup=kb
        )
        return

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        "Выбери действие в меню ниже:",
        reply_markup=main_menu_kb()
    )


@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: types.CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer(
            "✅ Спасибо за подписку!",
            reply_markup=main_menu_kb()
        )
    else:
        await call.answer("❌ Ты ещё не подписался на все каналы!", show_alert=True)


@dp.message(F.text == "🔍 Поиск юзернейма")
async def search_menu(message: types.Message):
    await message.answer("🔍 **Поиск юзернейма**\n\nВыбери раздел:",
                         reply_markup=search_menu_kb(),
                         parse_mode=ParseMode.MARKDOWN)


@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    user = await get_user(message.from_user.id)
    ref_count = user[2] if user else 0
    prem = user[3] if user and user[3] else "Нет"
    me = await bot.get_me()
    await message.answer(
        f"👤 **Твой профиль**\n\n"
        f"🆔 ID: `{message.from_user.id}`\n"
        f"👥 Рефералов: {ref_count}\n"
        f"💎 Премиум до: {prem}\n"
        f"🎯 Запросов осталось: {user[4] if user else 10}\n\n"
        f"🔗 Твоя ссылка:\n`https://t.me/{me.username}?start={message.from_user.id}`",
        parse_mode=ParseMode.MARKDOWN
    )


@dp.message(F.text == "💎 Премиум")
async def premium_menu(message: types.Message):
    user = await get_user(message.from_user.id)
    refs = user[2] if user else 0
    me = await bot.get_me()
    text = (
        "💎 **Премиум подписка**\n\n"
        "🔓 Разблокирует:\n"
        "• Фильтр\n"
        "• Ловушка\n"
        "• Похожие на слово\n\n"
        "**Стоимость:**\n"
        "🔸 1 день — 5 рефералов\n"
        "🔸 3 дня — 7 рефералов\n"
        "🔸 5 дней — 10 рефералов\n\n"
        f"👥 Твоих рефералов: **{refs}**\n\n"
        f"🔗 Твоя ссылка:\n`https://t.me/{me.username}?start={message.from_user.id}`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 1 день (5 реф.)", callback_data="buy_prem_1")],
        [InlineKeyboardButton(text="🔥 3 дня (7 реф.)", callback_data="buy_prem_3")],
        [InlineKeyboardButton(text="🔥 5 дней (10 реф.)", callback_data="buy_prem_5")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


@dp.callback_query(F.data.startswith("buy_prem_"))
async def cb_buy_premium(call: types.CallbackQuery):
    days = int(call.data.split("_")[2])
    required = {1: 5, 3: 7, 5: 10}[days]

    user = await get_user(call.from_user.id)
    refs = user[2] if user else 0

    if refs >= required:
        await spend_refs(call.from_user.id, required)
        await update_premium(call.from_user.id, days)
        await call.message.edit_text(
            f"✅ **Премиум на {days} дн. активирован!**\n\n"
            f"Списано: {required} рефералов.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await call.answer(
            f"❌ Недостаточно рефералов!\nНужно: {required}\nУ тебя: {refs}",
            show_alert=True
        )


@dp.callback_query(F.data.startswith("search_"))
async def cb_search(call: types.CallbackQuery):
    length = int(call.data.split("_")[1])
    await call.message.edit_text(f"🔎 Ищу свободный юзернейм из {length} букв...")

    await asyncio.sleep(1)

    result = await search_username(length)

    if result:
        text = (
            f"✅ **НИК НАЙДЕН!**\n\n"
            f"🔹 Юзернейм: {result['username']}\n"
            f"📊 Читабельность: {result['readability']}\n"
            f"💰 Примерная цена: {result['price']}\n"
            f"⚖️ Ликвидность: {result['liquidity']}\n"
            f"⚡️ Статус: {result['status']}\n\n"
            f"🖱 Следующий поиск через 2 сек"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Ещё поиск", callback_data=f"search_{length}")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back_to_main")]
        ])
        await call.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await call.message.edit_text(
            "❌ Свободных юзернеймов не найдено. Попробуй ещё раз.",
            reply_markup=search_menu_kb()
        )


@dp.callback_query(F.data.startswith("premium_"))
async def cb_premium_features(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)
    prem = user[3] if user and user[3] else None

    is_premium = False
    if prem:
        try:
            is_premium = datetime.strptime(prem, "%Y-%m-%d") > datetime.now()
        except ValueError:
            is_premium = False

    if not is_premium:
        await call.answer(
            "🔒 Эта функция доступна только с Премиум подпиской!",
            show_alert=True
        )
        return

    feature = call.data.split("_")[1]
    if feature == "filter":
        await call.answer("⚙️ Фильтр: в разработке", show_alert=True)
    elif feature == "trap":
        await call.answer("🪤 Ловушка: в разработке", show_alert=True)
    elif feature == "word":
        await call.answer("📖 Поиск похожих на слово: в разработке", show_alert=True)


@dp.callback_query(F.data == "back_to_main")
async def cb_back(call: types.CallbackQuery):
    await call.message.edit_text("Выбери раздел:", reply_markup=search_menu_kb())


# ========== АДМИН ПАНЕЛЬ ==========
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])
    await message.answer("👑 **Админ-панель**", reply_markup=kb)


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    total, premium = await get_stats()
    await call.message.answer(
        f"📊 **Статистика**\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"💎 С премиумом: {premium}"
    )


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer(
        "📢 Отправь сообщение для рассылки (текст следующего сообщения):"
    )


# ========== ЗАПУСК ==========
async def main():
    await init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
