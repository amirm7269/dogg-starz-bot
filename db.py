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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                price INTEGER,
                sort_order INTEGER DEFAULT 0
            )
        """)
        await db.commit()

    await _seed_default_products()


async def _seed_default_products():
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM products")
        row = await cur.fetchone()
        if row and row[0] > 0:
            return

        defaults = [
            ("stars", "100 استارز", 45000, 1),
            ("stars", "500 استارز", 210000, 2),
            ("stars", "1000 استارز", 400000, 3),
            ("stars", "2500 استارز", 950000, 4),
            ("gift_normal", "💝 گیفت قلب", 7000, 1),
            ("gift_normal", "🧸 گیفت تدی", 7000, 2),
            ("gift_normal", "🎂 گیفت کیک", 23000, 3),
            ("gift_normal", "🚀 گیفت سفینه", 23000, 4),
            ("premium", "پرمیوم 1 ماهه", 350000, 1),
            ("premium", "پرمیوم 3 ماهه", 950000, 2),
            ("premium", "پرمیوم 12 ماهه", 3200000, 3),
        ]
        await db.executemany(
            "INSERT INTO products (category, name, price, sort_order) VALUES (?, ?, ?, ?)",
            defaults
        )
        await db.commit()


async def get_products(category: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, price FROM products WHERE category = ? ORDER BY sort_order, id",
            (category,)
        )
        return await cur.fetchall()


async def get_product(product_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, category, name, price FROM products WHERE id = ?",
            (product_id,)
        )
        return await cur.fetchone()


async def add_product(category: str, name: str, price: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO products (category, name, price, sort_order) VALUES (?, ?, ?, 999)",
            (category, name, price)
        )
        await db.commit()
        return cur.lastrowid


async def update_product_price(product_id: int, price: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE products SET price = ? WHERE id = ?", (price, product_id))
        await db.commit()


async def update_product_name(product_id: int, name: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE products SET name = ? WHERE id = ?", (name, product_id))
        await db.commit()


async def delete_product(product_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
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
