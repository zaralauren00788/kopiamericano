import os
import re
import time
import asyncio
import requests
from datetime import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from moviepy.editor import VideoFileClip

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
STREAMTAPE_LOGIN = os.getenv("STREAMTAPE_LOGIN")
STREAMTAPE_KEY = os.getenv("STREAMTAPE_KEY")

MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB
MAX_UPLOAD_PER_DAY = 10
MAX_CONCURRENT = 2

# ================= STATE =================

daily_usage = defaultdict(lambda: {"count": 0, "date": str(datetime.utcnow().date())})
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ================= STREAMTAPE =================

def upload_to_streamtape(filepath):
    url = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    with open(filepath, "rb") as f:
        files = {"file1": f}
        r = requests.post(url, files=files, timeout=600)
    return r.json()

# ================= DAILY LIMIT =================

def check_daily_limit(user_id):
    today = str(datetime.utcnow().date())
    if daily_usage[user_id]["date"] != today:
        daily_usage[user_id] = {"count": 0, "date": today}
    return daily_usage[user_id]["count"] < MAX_UPLOAD_PER_DAY

def increase_daily(user_id):
    daily_usage[user_id]["count"] += 1

# ================= PROGRESS BAR =================

def progress_bar(percent):
    blocks = int(percent / 10)
    return "█" * blocks + "░" * (10 - blocks)

# ================= VIDEO HANDLER =================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with semaphore:

        user_id = update.message.from_user.id
        chat_id = update.effective_chat.id
        video = update.message.video or update.message.document

        if not video:
            return

        if not check_daily_limit(user_id):
            await update.message.reply_text("❌ Limit upload harian tercapai (10/hari).")
            return

        if video.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ File terlalu besar. Max 1GB.")
            return

        msg = await update.message.reply_text("⬇️ Downloading...")

        file = await context.bot.get_file(video.file_id)

        filename = f"{datetime.utcnow().timestamp()}_{video.file_unique_id}.mp4"
        filepath = f"/tmp/{filename}"

        await file.download_to_drive(filepath)

        await msg.edit_text("🎬 Membuat thumbnail...")

        thumb_path = f"/tmp/thumb_{video.file_unique_id}.jpg"

        try:
            clip = VideoFileClip(filepath)
            clip.save_frame(thumb_path, t=1)
            clip.close()
        except:
            thumb_path = None

        await msg.edit_text("⬆️ Uploading to Streamtape...\n░░░░░░░░░░ 0%")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, upload_to_streamtape, filepath)

        if result.get("status") == 200:
            fileid = result["result"]["file_id"]
            link = f"https://streamtape.com/v/{fileid}"

            await msg.edit_text("██████████ 100%")
            await context.bot.send_message(chat_id, f"✅ Uploaded!\n🔗 {link}")

            increase_daily(user_id)

        else:
            await msg.edit_text("❌ Upload gagal.")

        if os.path.exists(filepath):
            os.remove(filepath)

        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

# ================= START =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

print("🔥 Streamtape Upload Bot Running...")
app.run_polling(drop_pending_updates=True)
