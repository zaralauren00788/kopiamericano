import os
import re
import time
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DOOD_API_KEY = os.getenv("DOOD_API_KEY")

if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan!")

if not DOOD_API_KEY:
    raise ValueError("DOOD_API_KEY tidak ditemukan!")

COOLDOWN = 30
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

user_cooldowns = {}
queue = asyncio.Queue()

# ===== GET DIRECT LINK =====
def get_direct_link(url):
    api = f"https://doodapi.com/api/file/direct_link?key={DOOD_API_KEY}&url={url}"
    r = requests.get(api, timeout=30)
    data = r.json()
    if data.get("status") != 200:
        return None
    return data["result"]["download_url"]

# ===== DOWNLOAD FILE =====
def download_file(url, filename):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)

# ===== PROCESS DOWNLOAD =====
async def process_download(update: Update):
    text = update.message.text.strip()
    urls = re.findall(r'(https?://[^\s]+)', text)

    if not urls:
        await update.message.reply_text("❌ Link tidak valid.")
        return

    dood_url = urls[0]

    await update.message.reply_text("⏳ Mengambil direct link...")

    direct_link = await asyncio.to_thread(get_direct_link, dood_url)

    if not direct_link:
        await update.message.reply_text("❌ Gagal mendapatkan direct link.")
        return

    filename = "video.mp4"

    await update.message.reply_text("⬇️ Downloading...")

    await asyncio.to_thread(download_file, direct_link, filename)

    if os.path.getsize(filename) > MAX_FILE_SIZE:
        os.remove(filename)
        await update.message.reply_text("❌ File lebih dari 2GB.")
        return

    await update.message.reply_video(video=open(filename, "rb"))
    os.remove(filename)

    await update.message.reply_text("✅ Selesai.")

# ===== HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = time.time()

    if user_id in user_cooldowns:
        remaining = COOLDOWN - (now - user_cooldowns[user_id])
        if remaining > 0:
            await update.message.reply_text(f"⏳ Tunggu {int(remaining)} detik.")
            return

    user_cooldowns[user_id] = now

    await process_download(update)

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Dood Remote Bot Running...")
app.run_polling()
