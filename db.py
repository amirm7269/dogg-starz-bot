import aiosqlite
import config
import datetime
import random
import string


async def init_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                referrer_id INTEGER,
                joined_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id INTEGER,
                category TEXT,
                item TEXT,
                price INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS charge_requests (
                request_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await db.commit()


def _gen_id(prefix):
    rand = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}{rand}"


async def get_or_create_user(user_id: int, username: str, referrer_id: int = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, username, balance, referrer_id, joined_at) VALUES (?, ?, 0, ?, ?)",
                (user_id, username, referrer_id, datetime.datetime.utcnow().isoformat())
            )
            await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT user_id, username, balance, referrer_id, joined_at FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()


async def update_balance(user_id: int, delta: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        await db.commit()


async def create_order(user_id: int, category: str, item: str, price: int):
    order_id = _gen_id("ORD")
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO orders (order_id, user_id, category, item, price, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (order_id, user_id, category, item, price, datetime.datetime.utcnow().isoformat())
        )
        await db.commit()
    return order_id


async def get_user_orders(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT order_id, category, item, price, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 15",
            (user_id,)
        )
        return await cur.fetchall()


async def set_order_status(order_id: str, status: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
        await db.commit()


async def get_order(order_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT order_id, user_id, category, item, price, status FROM orders WHERE order_id = ?", (order_id,))
        return await cur.fetchone()


async def create_charge_request(user_id: int, amount: int):
    request_id = _gen_id("CHG")
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO charge_requests (request_id, user_id, amount, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (request_id, user_id, amount, datetime.datetime.utcnow().isoformat())
        )
        await db.commit()
    return request_id


async def get_charge_request(request_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT request_id, user_id, amount, status FROM charge_requests WHERE request_id = ?", (request_id,))
        return await cur.fetchone()


async def set_charge_status(request_id: str, status: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE charge_requests SET status = ? WHERE request_id = ?", (status, request_id))
        await db.commit()


async def count_referrals(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0
