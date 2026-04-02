import os
import asyncio
import requests
from datetime import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
STREAMTAPE_LOGIN = os.getenv("STREAMTAPE_LOGIN")
STREAMTAPE_KEY = os.getenv("STREAMTAPE_KEY")

MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB
MAX_UPLOAD_PER_DAY = 10
MAX_CONCURRENT_UPLOAD = 2

# ================= STATE =================

daily_usage = defaultdict(lambda: {
    "count": 0,
    "date": str(datetime.utcnow().date())
})

upload_semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOAD)

# ================= STREAMTAPE 2-STEP UPLOAD =================

def upload_to_streamtape(filepath):

    if not STREAMTAPE_LOGIN or not STREAMTAPE_KEY:
        return {"status": "error", "message": "STREAMTAPE_LOGIN atau STREAMTAPE_KEY belum diset"}

    try:
        # STEP 1: Request upload server
        server_req = requests.get(
            f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}",
            timeout=60
        )

        if not server_req.ok:
            return {"status": "error", "message": f"Server request gagal: {server_req.text[:200]}"}

        server_json = server_req.json()

        if server_json.get("status") != 200:
            return {"status": "error", "message": str(server_json)}

        upload_url = server_json["result"]["url"]

        # STEP 2: Upload file ke upload server
        with open(filepath, "rb") as f:
            files = {"file1": f}
            upload_req = requests.post(upload_url, files=files, timeout=1800)

        if not upload_req.ok:
            return {"status": "error", "message": f"Upload gagal: {upload_req.text[:200]}"}

        if not upload_req.text:
            return {"status": "error", "message": "Empty response saat upload"}

        return upload_req.json()

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ================= DAILY LIMIT =================

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

# ================= HANDLER =================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    async with upload_semaphore:

        user = update.message.from_user
        video = update.message.video or update.message.document

        if not video:
            return

        # LIMIT CHECK
        if not check_daily_limit(user.id):
            await update.message.reply_text("❌ Limit upload harian tercapai (10 per hari).")
            return

        # SIZE CHECK
        if video.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ File terlalu besar. Maksimal 1GB.")
            return

        status_msg = await update.message.reply_text("⬇️ Downloading...")

        filepath = None

        try:
            tg_file = await context.bot.get_file(video.file_id)

            filename = f"{datetime.utcnow().timestamp()}_{video.file_unique_id}.mp4"
            filepath = f"/tmp/{filename}"

            await tg_file.download_to_drive(filepath)

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
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

# ================= MAIN =================

if not TOKEN:
    print("BOT_TOKEN belum diset.")
    exit()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(
    MessageHandler(
        filters.VIDEO | filters.Document.VIDEO,
        handle_video
    )
)

print("🔥 Streamtape Upload Bot Running...")

app.run_polling(
    drop_pending_updates=True,
    allowed_updates=Update.ALL_TYPES
)
