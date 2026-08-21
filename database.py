import sqlite3
import random
import string
from datetime import datetime

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        stars_spent INTEGER DEFAULT 0,
        reg_date TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER DEFAULT NULL,
        created_at TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tariff TEXT,
        stars_paid INTEGER,
        promo_code TEXT,
        date TEXT
    )
    """)
    conn.commit()
    
    # Добавляем 20 тестовых промо
    cursor.execute("SELECT COUNT(*) FROM promo_codes")
    if cursor.fetchone()[0] == 0:
        for _ in range(20):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            cursor.execute("INSERT INTO promo_codes (code, created_at) VALUES (?, ?)", 
                           (code, datetime.now().isoformat()))
        conn.commit()

def get_free_promo():
    cursor.execute("SELECT code FROM promo_codes WHERE is_used=0 LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None

def use_promo(code, user_id):
    cursor.execute("UPDATE promo_codes SET is_used=1, used_by=? WHERE code=?", (user_id, code))
    conn.commit()
    return cursor.rowcount > 0

def add_promo_codes(codes_list):
    added = 0
    for code in codes_list:
        try:
            cursor.execute("INSERT INTO promo_codes (code, created_at) VALUES (?, ?)", 
                           (code, datetime.now().isoformat()))
            added += 1
        except:
            pass
    conn.commit()
    return added

def delete_promo(code):
    cursor.execute("DELETE FROM promo_codes WHERE code=?", (code,))
    conn.commit()
    return cursor.rowcount > 0

def get_all_promos(limit=50):
    cursor.execute("SELECT code, is_used, used_by FROM promo_codes LIMIT ?", (limit,))
    return cursor.fetchall()

def add_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (id, username, reg_date) VALUES (?, ?, ?)",
                   (user_id, username, datetime.now().isoformat()))
    conn.commit()

def add_purchase(user_id, tariff, stars, promo):
    cursor.execute("INSERT INTO purchases (user_id, tariff, stars_paid, promo_code, date) VALUES (?, ?, ?, ?, ?)",
                   (user_id, tariff, stars, promo, datetime.now().isoformat()))
    conn.commit()

def get_user_purchases(user_id):
    cursor.execute("SELECT tariff, promo_code, date FROM purchases WHERE user_id=? ORDER BY date DESC LIMIT 5", (user_id,))
    return cursor.fetchall()

def get_stats():
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_purchases = cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    total_stars = cursor.execute("SELECT SUM(stars_paid) FROM purchases").fetchone()[0] or 0
    free_promos = cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_used=0").fetchone()[0]
    return total_users, total_purchases, total_stars, free_promos

def get_all_users(limit=20):
    cursor.execute("SELECT id, username, stars_spent, reg_date FROM users ORDER BY reg_date DESC LIMIT ?", (limit,))
    return cursor.fetchall()
