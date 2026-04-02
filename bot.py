import os
import re
import time
import asyncio
import requests
from collections import deque
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DOOD_API_KEY = os.getenv("DOOD_API_KEY")

if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan!")

if not DOOD_API_KEY:
    raise ValueError("DOOD_API_KEY tidak ditemukan!")

# ===== SETTINGS =====
COOLDOWN = 30  # detik per user
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
# ====================

user_cooldowns = {}
queue = deque()
is_processing = False

# === GET DIRECT LINK FROM DOOD ===
def get_direct_link(url):
    api_url = f"https://doodapi.com/api/file/direct_link?key={DOOD_API_KEY}&url={url}"
    response = requests.get(api_url)
    data = response.json()

    if data["status"] != 200:
        return None

    return data["result"]["download_url"]

# === DOWNLOAD FILE ===
def download_file(url, filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

# === PROCESS QUEUE ===
async def process_queue(app):
    global is_processing

    if is_processing:
        return

    is_processing = True

    while queue:
        update = queue.popleft()
        await handle_download(update, app)

    is_processing = False

# === HANDLE DOWNLOAD ===
async def handle_download(update, app):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    await update.message.reply_text("⏳ Mengambil direct link...")

    try:
        direct_link = get_direct_link(text)

        if not direct_link:
            await update.message.reply_text("❌ Gagal ambil link.")
            return

        filename = "video.mp4"

        await update.message.reply_text("⬇️ Downloading...")

        download_file(direct_link, filename)

        file_size = os.path.getsize(filename)

        if file_size > MAX_FILE_SIZE:
            os.remove(filename)
            await update.message.reply_text("❌ File lebih dari 2GB.")
            return

        await update.message.reply_video(video=open(filename, "rb"))

        os.remove(filename)

        await update.message.reply_text("✅ Selesai.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

# === MAIN HANDLER ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global queue

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    # Auto detect dood variations
    if not re.search(r"(dood\.\w+)", text):
        await update.message.reply_text("Kirim link DoodStream.")
        return

    # Cooldown check
    now = time.time()
    if user_id in user_cooldowns:
        remaining = COOLDOWN - (now - user_cooldowns[user_id])
        if remaining > 0:
            await update.message.reply_text(f"⏳ Tunggu {int(remaining)} detik lagi.")
            return

    user_cooldowns[user_id] = now

    queue.append(update)
    await update.message.reply_text("📥 Masuk antrian...")

    asyncio.create_task(process_queue(context.application))

# === RUN APP ===
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("DoodStream Remote Bot Running...")
app.run_polling()
