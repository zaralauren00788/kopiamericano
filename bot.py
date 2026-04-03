import os
import sqlite3
import string
import random
import time
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7688712382
FORCE_CHANNELS = ["@viral17menit", "@doodstreamviral2026"]
DB_NAME = "ultra_files.db"


# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            code TEXT PRIMARY KEY,
            file_id TEXT,
            views INTEGER,
            expire_at INTEGER
        )
    """)
    conn.commit()
    conn.close()


def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def save_file(code, file_id, expire_seconds):
    expire_at = int(time.time()) + expire_seconds
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO files (code, file_id, views, expire_at) VALUES (?, ?, ?, ?)",
        (code, file_id, 0, expire_at)
    )
    conn.commit()
    conn.close()


def get_file(code):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT file_id, views, expire_at FROM files WHERE code=?", (code,))
    result = c.fetchone()
    conn.close()
    return result


def add_view(code):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE files SET views = views + 1 WHERE code=?", (code,))
    conn.commit()
    conn.close()


# ================= FORCE JOIN =================
async def check_force_join(user_id, bot):
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Kirim video (admin only).")
        return

    code = context.args[0]

    joined = await check_force_join(user_id, context.bot)
    if not joined:
        channels = "\n".join(FORCE_CHANNELS)
        await update.message.reply_text(
            f"🚫 Kamu harus join dulu:\n{channels}\n\nKlik ulang link setelah join."
        )
        return

    data = get_file(code)
    if not data:
        await update.message.reply_text("❌ File tidak ditemukan.")
        return

    file_id, views, expire_at = data

    if int(time.time()) > expire_at:
        await update.message.reply_text("⏰ Link sudah expired.")
        return

    add_view(code)

    msg = await update.message.reply_video(file_id)

    # Auto delete setelah 5 menit
    await asyncio.sleep(300)
    try:
        await msg.delete()
    except:
        pass


# ================= ADMIN UPLOAD =================
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    video = update.message.video or update.message.document
    if not video:
        return

    file_id = video.file_id
    code = generate_code()

    expire_seconds = 86400  # 1 hari (ubah sesuai mau)
    save_file(code, file_id, expire_seconds)

    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"

    await update.message.reply_text(
        f"✅ Link dibuat\n\n"
        f"🔗 {link}\n"
        f"⏳ Expire: 24 Jam"
    )


# ================= STATS =================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM files")
    total = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(f"📊 Total Files: {total}")


# ================= MAIN =================
def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, upload))

    app.run_polling()


if __name__ == "__main__":
    main()
