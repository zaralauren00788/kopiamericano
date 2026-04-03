import os
import asyncio
import requests
import aiosqlite
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
LOGIN = os.getenv("STREAMTAPE_LOGIN")
KEY = os.getenv("STREAMTAPE_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "2"))

DB_NAME = "database.db"
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ================= DATABASE =================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_vip INTEGER DEFAULT 0,
            daily_limit INTEGER DEFAULT 10,
            used_today INTEGER DEFAULT 0,
            last_reset TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            status TEXT DEFAULT 'pending',
            result_link TEXT,
            created_at TEXT
        )
        """)
        await db.commit()

# ================= RESET DAILY LIMIT =================

async def check_reset(user_id):
    today = datetime.utcnow().date()

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT last_reset FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cursor.fetchone()

        if not row or not row[0]:
            await db.execute(
                "UPDATE users SET used_today=0, last_reset=? WHERE user_id=?",
                (str(today), user_id)
            )
        else:
            last = datetime.fromisoformat(row[0]).date()
            if last != today:
                await db.execute(
                    "UPDATE users SET used_today=0, last_reset=? WHERE user_id=?",
                    (str(today), user_id)
                )

        await db.commit()

# ================= STREAMTAPE REMOTE =================

def remote_upload(url):
    api = f"https://api.streamtape.com/remotedl/add?login={LOGIN}&key={KEY}&url={url}"
    r = requests.get(api, timeout=60)
    return r.json()

# ================= WORKER =================

async def worker(app):
    while True:
        async with semaphore:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute(
                    "SELECT id, user_id, url FROM queue WHERE status='pending' ORDER BY id ASC LIMIT 1"
                )
                job = await cursor.fetchone()

                if job:
                    job_id, user_id, url = job

                    await db.execute(
                        "UPDATE queue SET status='uploading' WHERE id=?",
                        (job_id,)
                    )
                    await db.commit()

                    try:
                        result = remote_upload(url)

                        if result.get("status") == 200:
                            file_id = result["result"]["file_id"]
                            link = f"https://streamtape.com/v/{file_id}"

                            await db.execute(
                                "UPDATE queue SET status='done', result_link=? WHERE id=?",
                                (link, job_id)
                            )
                            await db.commit()

                            await app.bot.send_message(
                                user_id,
                                f"✅ Upload selesai:\n{link}"
                            )
                        else:
                            raise Exception(str(result))

                    except Exception as e:
                        await db.execute(
                            "UPDATE queue SET status='failed' WHERE id=?",
                            (job_id,)
                        )
                        await db.commit()

                        await app.bot.send_message(
                            user_id,
                            f"❌ Upload gagal:\n{e}"
                        )

        await asyncio.sleep(3)

# ================= HANDLER =================

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    url = update.message.text.strip()

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, last_reset) VALUES (?, ?)",
            (user_id, str(datetime.utcnow().date()))
        )
        await db.commit()

    await check_reset(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT daily_limit, used_today FROM users WHERE user_id=?",
            (user_id,)
        )
        user = await cursor.fetchone()

        limit, used = user

        if used >= limit:
            await update.message.reply_text("❌ Limit upload harian habis.")
            return

        await db.execute(
            "INSERT INTO queue (user_id, url, created_at) VALUES (?, ?, ?)",
            (user_id, url, str(datetime.utcnow()))
        )

        await db.execute(
            "UPDATE users SET used_today = used_today + 1 WHERE user_id=?",
            (user_id,)
        )

        await db.commit()

    await update.message.reply_text("📦 Link masuk antrian upload...")

# ================= ADMIN COMMAND =================

async def add_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Format: /vip user_id")
        return

    target_id = int(context.args[0])

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET is_vip=1, daily_limit=100 WHERE user_id=?",
            (target_id,)
        )
        await db.commit()

    await update.message.reply_text("👑 User dijadikan VIP.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM queue WHERE status='pending'"
        )
        pending = (await cursor.fetchone())[0]

    await update.message.reply_text(f"📦 Antrian pending: {pending}")

# ================= MAIN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
app.add_handler(CommandHandler("vip", add_vip))
app.add_handler(CommandHandler("status", status))

async def main():
    await init_db()
    asyncio.create_task(worker(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
