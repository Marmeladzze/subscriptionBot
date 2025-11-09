import aiosqlite
from datetime import datetime, timedelta

DB_NAME = 'bot_database.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                subscription_end_date TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tariffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                duration_days INTEGER NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tariff_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                duration_days INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                telegram_payment_id TEXT UNIQUE NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_text TEXT UNIQUE NOT NULL,
                discount_percent INTEGER NOT NULL,
                max_uses INTEGER NOT NULL,
                uses_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('channel_id', '-100...'))
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('welcome_photo_id', ''))
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('about_text', 'Это текст по умолчанию об информации. Измените его в админ-панели.'))

        await db.commit()

async def create_promo_code(code_text, discount, max_uses):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO promo_codes (code_text, discount_percent, max_uses) VALUES (?, ?, ?)",
            (code_text.upper(), discount, max_uses)
        )
        await db.commit()

async def get_promo_code_details(code_text):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, discount_percent, max_uses, uses_count, is_active FROM promo_codes WHERE code_text = ?",
            (code_text.upper(),)
        )
        return await cursor.fetchone()

async def get_all_promo_codes():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, code_text, discount_percent, uses_count, max_uses, is_active FROM promo_codes")
        return await cursor.fetchall()

async def toggle_promo_code_activity(promo_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE promo_codes SET is_active = NOT is_active WHERE id = ?", (promo_id,))
        await db.commit()

async def increment_promo_code_use(code_text):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE promo_codes SET uses_count = uses_count + 1 WHERE code_text = ?",
            (code_text.upper(),)
        )
        await db.commit()

async def get_sales_for_period(days=None):
    async with aiosqlite.connect(DB_NAME) as db:
        if days:
            start_date = datetime.now() - timedelta(days=days)
            query = "SELECT SUM(price), COUNT(id) FROM payments WHERE payment_date >= ?"
            cursor = await db.execute(query, (start_date.strftime("%Y-%m-%d %H:%M:%S"),))
        else:
            query = "SELECT SUM(price), COUNT(id) FROM payments"
            cursor = await db.execute(query)
        result = await cursor.fetchone()
        return (result[0] or 0, result[1])

async def get_most_popular_tariff():
    async with aiosqlite.connect(DB_NAME) as db:
        query = "SELECT tariff_name, COUNT(id) as sales_count FROM payments GROUP BY tariff_name ORDER BY sales_count DESC LIMIT 1"
        cursor = await db.execute(query)
        return await cursor.fetchone()

async def get_user_subscription(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT subscription_end_date FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else None

async def get_users_nearing_expiry(days_left):
    target_date_start = datetime.now() + timedelta(days=days_left - 1)
    target_date_end = datetime.now() + timedelta(days=days_left)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE subscription_end_date BETWEEN ? AND ?", (target_date_start.strftime("%Y-%m-%d %H:%M:%S"), target_date_end.strftime("%Y-%m-%d %H:%M:%S")))
        return await cursor.fetchall()

async def add_payment_record(user_id, tariff_name, price, duration, payment_id):
    async with aiosqlite.connect(DB_NAME) as db:
        payment_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("INSERT INTO payments (user_id, tariff_name, price, duration_days, payment_date, telegram_payment_id) VALUES (?, ?, ?, ?, ?, ?)", (user_id, tariff_name, price, duration, payment_date, payment_id))
        await db.commit()

async def get_tariff_details(tariff_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT name, price, duration_days FROM tariffs WHERE id = ?", (tariff_id,))
        return await cursor.fetchone()

async def get_setting(key):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = await cursor.fetchone()
        return result[0] if result else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        await db.commit()

async def add_tariff(name, price, duration):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO tariffs (name, price, duration_days) VALUES (?, ?, ?)", (name, price, duration))
        await db.commit()

async def get_all_tariffs():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, name, price, duration_days FROM tariffs")
        return await cursor.fetchall()

async def delete_tariff(tariff_id):
     async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM tariffs WHERE id = ?", (tariff_id,))
        await db.commit()

async def add_user(user_id, username):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()

# --- ЭТА ФУНКЦИЯ ЗАМЕНЕНА НА "УМНУЮ" ВЕРСИЮ ---
async def update_subscription(user_id, days_to_add):
    """Продлевает или выдает подписку, добавляя дни к текущей дате окончания."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT subscription_end_date FROM users WHERE user_id = ?", (user_id,))
        current_end_date_str = (await cursor.fetchone())[0]
        
        start_date = datetime.now()
        # Если подписка уже есть и она активна, точкой отсчета становится ее дата окончания
        if current_end_date_str:
            current_end_date = datetime.strptime(current_end_date_str, "%Y-%m-%d %H:%M:%S")
            if current_end_date > start_date:
                start_date = current_end_date
        
        new_end_date = start_date + timedelta(days=days_to_add)
        
        await db.execute(
            "UPDATE users SET subscription_end_date = ? WHERE user_id = ?",
            (new_end_date.strftime("%Y-%m-%d %H:%M:%S"), user_id)
        )
        await db.commit()
        # Возвращаем новую дату, чтобы показать ее пользователю
        return new_end_date

# --- ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ ---
async def get_expired_users():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE subscription_end_date IS NOT NULL AND subscription_end_date < ?", (now,))
        expired = await cursor.fetchall()
        for user_id in expired:
            await db.execute("UPDATE users SET subscription_end_date = NULL WHERE user_id = ?", (user_id[0],))
        await db.commit()
        return expired

async def get_all_user_ids():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        return [row[0] for row in await cursor.fetchall()]

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        total_users = await db.execute("SELECT COUNT(*) FROM users")
        total_users_count = (await total_users.fetchone())[0]
        active_subs = await db.execute("SELECT COUNT(*) FROM users WHERE subscription_end_date > ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        active_subs_count = (await active_subs.fetchone())[0]
        return total_users_count, active_subs_count

async def get_user_profile(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, username, subscription_end_date FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def manually_update_subscription(user_id, days_to_add):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT subscription_end_date FROM users WHERE user_id = ?", (user_id,))
        current_end_date_str = (await cursor.fetchone())[0]
        start_date = datetime.now()
        if current_end_date_str:
            current_end_date = datetime.strptime(current_end_date_str, "%Y-%m-%d %H:%M:%S")
            if current_end_date > start_date:
                start_date = current_end_date
        new_end_date = start_date + timedelta(days=days_to_add)
        await db.execute("UPDATE users SET subscription_end_date = ? WHERE user_id = ?", (new_end_date.strftime("%Y-%m-%d %H:%M:%S"), user_id))
        await db.commit()
        return new_end_date

async def revoke_subscription(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET subscription_end_date = NULL WHERE user_id = ?", (user_id,))
        await db.commit()