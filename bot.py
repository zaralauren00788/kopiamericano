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

# ================= STREAMTAPE UPLOAD (2 STEP SAFE) =================

def upload_to_streamtape(filepath):

    if not STREAMTAPE_LOGIN or not STREAMTAPE_KEY:
        return {"error": "STREAMTAPE_LOGIN atau STREAMTAPE_KEY belum diset di Railway"}

    try:
        # STEP 1: Request upload server
        server_req = requests.get(
            f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}",
            timeout=60
        )

        if not server_req.ok:
            return {"error": f"Gagal request upload server: {server_req.text[:300]}"}

        try:
            server_json = server_req.json()
        except:
            return {"error": f"Response bukan JSON:\n{server_req.text[:300]}"}

        if server_json.get("status") != 200:
            return {"error": f"API Error:\n{server_json}"}

        upload_url = server_json.get("result", {}).get("url")

        if not upload_url:
            return {"error": f"Tidak ada upload URL:\n{server_json}"}

        # STEP 2: Upload file
        with open(filepath, "rb") as f:
            files = {"file1": f}
            upload_req = requests.post(upload_url, files=files, timeout=1800)

        if not upload_req.ok:
            return {"error": f"Upload gagal:\n{upload_req.text[:300]}"}

        try:
            upload_json = upload_req.json()
        except:
            return {"error": f"Upload response bukan JSON:\n{upload_req.text[:300]}"}

        return upload_json

    except Exception as e:
        return {"error": str(e)}

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

# ================= VIDEO HANDLER =================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    async with upload_semaphore:

        user = update.message.from_user
        video = update.message.video or update.message.document

        if not video:
            return

        # LIMIT
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

            # HANDLE ERROR
            if result.get("error"):
                await status_msg.edit_text(f"❌ Upload gagal:\n\n{result['error']}")
                return

            # VALIDATE SUCCESS
            if result.get("status") == 200:
                file_id = result.get("result", {}).get("file_id")

                if not file_id:
                    await status_msg.edit_text(
                        f"❌ Upload gagal.\n\nResponse tidak mengandung file_id:\n{result}"
                    )
                    return

                link = f"https://streamtape.com/v/{file_id}"

                await status_msg.edit_text("✅ Upload berhasil!")
                await update.message.reply_text(f"🔗 {link}")

                increase_daily(user.id)
            else:
                await status_msg.edit_text(f"❌ Upload gagal.\n\nResponse:\n{result}")

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
