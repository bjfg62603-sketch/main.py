import aiosqlite
from datetime import datetime, timedelta

DB_NAME = "syndicate.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                referrer_id INTEGER,
                ref_count INTEGER DEFAULT 0,
                premium_until TEXT,
                requests_left INTEGER DEFAULT 10,
                username TEXT
            )
        """)
        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def add_user(user_id, username=None, referrer_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
            (user_id, username, referrer_id)
        )
        if referrer_id and referrer_id != user_id:
            await db.execute(
                "UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?",
                (referrer_id,)
            )
        await db.commit()


async def update_premium(user_id, days):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT premium_until FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            current = row[0] if row and row[0] else None

        if current:
            try:
                base_date = datetime.strptime(current, "%Y-%m-%d")
            except ValueError:
                base_date = datetime.now()
        else:
            base_date = datetime.now()

        new_date = base_date + timedelta(days=days)
        await db.execute(
            "UPDATE users SET premium_until = ? WHERE user_id = ?",
            (new_date.strftime("%Y-%m-%d"), user_id)
        )
        await db.commit()


async def spend_refs(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET ref_count = ref_count - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            return await cursor.fetchall()


async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE premium_until IS NOT NULL") as cursor:
            premium = (await cursor.fetchone())[0]
        return total, premium
