import os
import asyncio
import requests
from datetime import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ================== CONFIG ==================

TOKEN = os.getenv("BOT_TOKEN")
STREAMTAPE_LOGIN = os.getenv("STREAMTAPE_LOGIN")
STREAMTAPE_KEY = os.getenv("STREAMTAPE_KEY")

MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB
MAX_UPLOAD_PER_DAY = 10
MAX_CONCURRENT_UPLOAD = 2

# ================== STATE ==================

daily_usage = defaultdict(lambda: {
    "count": 0,
    "date": str(datetime.utcnow().date())
})

upload_semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOAD)

# ================== STREAMTAPE UPLOAD ==================

def upload_to_streamtape(filepath):

    if not STREAMTAPE_LOGIN or not STREAMTAPE_KEY:
        return {"status": "error", "message": "STREAMTAPE_LOGIN atau STREAMTAPE_KEY belum di set di Railway."}

    url = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"

    try:
        with open(filepath, "rb") as f:
            files = {"file1": f}
            response = requests.post(url, files=files, timeout=600)

        if not response.text:
            return {"status": "error", "message": "Empty response dari Streamtape"}

        try:
            return response.json()
        except Exception:
            return {"status": "error", "message": f"Invalid JSON response:\n{response.text[:300]}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ================== LIMIT SYSTEM ==================

def check_daily_limit(user_id):
    today = str(datetime.utcnow().date())

    if daily_usage[user_id]["date"] != today:
        daily_usage[user_id] = {
            "count": 0,
            "date": today
        }

    return daily_usage[user_id]["count"] < MAX_UPLOAD_PER_DAY

def increase_daily(user_id):
    daily_usage[user_id]["count"] += 1

# ================== HANDLER ==================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    async with upload_semaphore:

        user = update.message.from_user
        video = update.message.video or update.message.document

        if not video:
            return

        # DAILY LIMIT
        if not check_daily_limit(user.id):
            await update.message.reply_text("❌ Limit upload harian tercapai (10 per hari).")
            return

        # SIZE CHECK
        if video.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ File terlalu besar. Maksimal 1GB.")
            return

        status_msg = await update.message.reply_text("⬇️ Downloading...")

        try:
            telegram_file = await context.bot.get_file(video.file_id)

            filename = f"{datetime.utcnow().timestamp()}_{video.file_unique_id}.mp4"
            filepath = f"/tmp/{filename}"

            await telegram_file.download_to_drive(filepath)

            await status_msg.edit_text("⬆️ Uploading ke Streamtape...")

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, upload_to_streamtape, filepath)

            if isinstance(result.get("status"), int) and result.get("status") == 200:
                file_id = result["result"]["file_id"]
                link = f"https://streamtape.com/v/{file_id}"

                await status_msg.edit_text("✅ Upload berhasil!")
                await update.message.reply_text(f"🔗 {link}")

                increase_daily(user.id)

            else:
                error_msg = result.get("message", "Unknown error")
                await status_msg.edit_text(f"❌ Upload gagal.\n\n{error_msg}")

        except Exception as e:
            await status_msg.edit_text(f"❌ Terjadi error:\n{str(e)}")

        finally:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)

# ================== MAIN ==================

if not TOKEN:
    print("BOT_TOKEN belum di set.")
    exit()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

print("🔥 Streamtape Upload Bot Running...")
app.run_polling(drop_pending_updates=True)
