import asyncpg
import config
import datetime
import random
import string

_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance BIGINT DEFAULT 0,
                referrer_id BIGINT,
                joined_at TEXT
            )
        """)
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS kyc_verified BOOLEAN DEFAULT FALSE")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id BIGINT,
                category TEXT,
                item TEXT,
                price BIGINT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS completed_at TEXT")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS charge_requests (
                request_id TEXT PRIMARY KEY,
                user_id BIGINT,
                amount BIGINT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await conn.execute("ALTER TABLE charge_requests ADD COLUMN IF NOT EXISTS phone TEXT")
        await conn.execute("ALTER TABLE charge_requests ADD COLUMN IF NOT EXISTS kind TEXT DEFAULT 'normal'")
        await conn.execute("ALTER TABLE charge_requests ADD COLUMN IF NOT EXISTS card_number TEXT")
        await conn.execute("ALTER TABLE charge_requests ADD COLUMN IF NOT EXISTS card_photo_id TEXT")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_cards (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                card_number TEXT,
                card_photo_id TEXT,
                created_at TEXT
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                category TEXT,
                name TEXT,
                price BIGINT,
                sort_order INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

    await _seed_default_products()


async def _seed_default_products():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        if count and count > 0:
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
        await conn.executemany(
            "INSERT INTO products (category, name, price, sort_order) VALUES ($1, $2, $3, $4)",
            defaults
        )


async def get_products(category: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, price FROM products WHERE category = $1 ORDER BY sort_order, id",
            category
        )
        return [(r["id"], r["name"], r["price"]) for r in rows]


async def get_product(product_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT id, category, name, price FROM products WHERE id = $1",
            product_id
        )
        return (r["id"], r["category"], r["name"], r["price"]) if r else None


async def add_product(category: str, name: str, price: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        new_id = await conn.fetchval(
            "INSERT INTO products (category, name, price, sort_order) VALUES ($1, $2, $3, 999) RETURNING id",
            category, name, price
        )
        return new_id


async def update_product_price(product_id: int, price: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET price = $1 WHERE id = $2", price, product_id)


async def update_product_name(product_id: int, name: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET name = $1 WHERE id = $2", name, product_id)


async def delete_product(product_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM products WHERE id = $1", product_id)


def _gen_id(prefix):
    rand = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}{rand}"


async def get_or_create_user(user_id: int, username: str, referrer_id: int = None):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT user_id FROM users WHERE user_id = $1", user_id)
        if existing is None:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, referrer_id, joined_at) VALUES ($1, $2, 0, $3, $4)",
                user_id, username, referrer_id, datetime.datetime.utcnow().isoformat()
            )


async def get_user(user_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT user_id, username, balance, referrer_id, joined_at, kyc_verified, phone FROM users WHERE user_id = $1",
            user_id
        )
        return (r["user_id"], r["username"], r["balance"], r["referrer_id"], r["joined_at"], r["kyc_verified"], r["phone"]) if r else None


async def set_kyc_verified(user_id: int, verified: bool = True):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET kyc_verified = $1 WHERE user_id = $2", verified, user_id)


async def set_user_phone(user_id: int, phone: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone = $1 WHERE user_id = $2", phone, user_id)


async def update_balance(user_id: int, delta: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", delta, user_id)


async def create_order(user_id: int, category: str, item: str, price: int):
    order_id = _gen_id("ORD")
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO orders (order_id, user_id, category, item, price, status, created_at) VALUES ($1, $2, $3, $4, $5, 'pending', $6)",
            order_id, user_id, category, item, price, datetime.datetime.utcnow().isoformat()
        )
    return order_id


async def get_user_orders(user_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT order_id, category, item, price, status, created_at FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 15",
            user_id
        )
        return [(r["order_id"], r["category"], r["item"], r["price"], r["status"], r["created_at"]) for r in rows]


async def set_order_status(order_id: str, status: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if status == "done":
            await conn.execute(
                "UPDATE orders SET status = $1, completed_at = $2 WHERE order_id = $3",
                status, datetime.datetime.utcnow().isoformat(), order_id
            )
        else:
            await conn.execute("UPDATE orders SET status = $1 WHERE order_id = $2", status, order_id)


async def get_order(order_id: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT order_id, user_id, category, item, price, status, created_at, completed_at FROM orders WHERE order_id = $1",
            order_id
        )
        if not r:
            return None
        return (r["order_id"], r["user_id"], r["category"], r["item"], r["price"], r["status"], r["created_at"], r["completed_at"])


async def create_charge_request(user_id: int, amount: int, phone: str = None, kind: str = "normal",
                                  status: str = "pending", card_number: str = None, card_photo_id: str = None):
    request_id = _gen_id("CHG")
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO charge_requests (request_id, user_id, amount, status, created_at, phone, kind, card_number, card_photo_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            request_id, user_id, amount, status, datetime.datetime.utcnow().isoformat(), phone, kind, card_number, card_photo_id
        )
    return request_id


async def get_charge_request(request_id: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT request_id, user_id, amount, status, phone, kind, card_number, card_photo_id FROM charge_requests WHERE request_id = $1",
            request_id
        )
        if not r:
            return None
        return (r["request_id"], r["user_id"], r["amount"], r["status"], r["phone"], r["kind"], r["card_number"], r["card_photo_id"])


async def get_awaiting_receipt(user_id: int):
    """آخرین درخواست شارژی که احراز هویتش تایید شده و منتظر عکس رسیده"""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT request_id, user_id, amount, status, phone, kind, card_number, card_photo_id FROM charge_requests "
            "WHERE user_id = $1 AND status = 'awaiting_receipt' ORDER BY created_at DESC LIMIT 1",
            user_id
        )
        if not r:
            return None
        return (r["request_id"], r["user_id"], r["amount"], r["status"], r["phone"], r["kind"], r["card_number"], r["card_photo_id"])


async def add_user_card(user_id: int, card_number: str, card_photo_id: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        new_id = await conn.fetchval(
            "INSERT INTO user_cards (user_id, card_number, card_photo_id, created_at) VALUES ($1, $2, $3, $4) RETURNING id",
            user_id, card_number, card_photo_id, datetime.datetime.utcnow().isoformat()
        )
        return new_id


async def get_user_cards(user_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, card_number, card_photo_id FROM user_cards WHERE user_id = $1 ORDER BY id",
            user_id
        )
        return [(r["id"], r["card_number"], r["card_photo_id"]) for r in rows]


async def get_user_card(card_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT id, user_id, card_number, card_photo_id FROM user_cards WHERE id = $1",
            card_id
        )
        return (r["id"], r["user_id"], r["card_number"], r["card_photo_id"]) if r else None


async def set_charge_status(request_id: str, status: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE charge_requests SET status = $1 WHERE request_id = $2", status, request_id)


async def count_referrals(user_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE referrer_id = $1", user_id)
        return count if count else 0


async def get_setting(key: str, default=None):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        value = await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)
        return value if value is not None else default


async def set_setting(key: str, value: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2) "
            "ON CONFLICT (key) DO UPDATE SET value = $2",
            key, str(value)
        )
