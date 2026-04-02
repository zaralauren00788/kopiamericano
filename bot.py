import os
import re
import time
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
STREAMTAPE_LOGIN = os.getenv("STREAMTAPE_LOGIN")
STREAMTAPE_KEY = os.getenv("STREAMTAPE_KEY")

if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan!")

if not STREAMTAPE_LOGIN or not STREAMTAPE_KEY:
    raise ValueError("Streamtape login/key belum di-set!")

COOLDOWN = 30
user_cooldowns = {}

# =========================
# STREAMTAPE API
# =========================

def remote_add(url):
    api = f"https://api.streamtape.com/remotedl/add?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}&url={url}"
    r = requests.get(api, timeout=60)
    return r.json()

def remote_status():
    api = f"https://api.streamtape.com/remotedl/status?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    r = requests.get(api, timeout=60)
    return r.json()

def upload_file(filepath):
    api = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    with open(filepath, "rb") as f:
        files = {"file1": f}
        r = requests.post(api, files=files, timeout=600)
    return r.json()

# =========================
# HANDLE URL (REMOTE)
# =========================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = time.time()

    if user_id in user_cooldowns:
        remaining = COOLDOWN - (now - user_cooldowns[user_id])
        if remaining > 0:
            await update.message.reply_text(f"⏳ Tunggu {int(remaining)} detik.")
            return

    user_cooldowns[user_id] = now

    urls = re.findall(r'(https?://[^\s]+)', update.message.text)

    if not urls:
        await update.message.reply_text("❌ Kirim link yang valid.")
        return

    await update.message.reply_text("🚀 Menambahkan ke remote upload...")

    add_result = remote_add(urls[0])

    if add_result.get("status") != 200:
        await update.message.reply_text("❌ Gagal menambahkan remote upload.")
        return

    await update.message.reply_text("⏳ Menunggu proses selesai...")

    # Tunggu sampai selesai (maks 5 menit)
    for _ in range(30):
        await asyncio.sleep(10)
        status_result = remote_status()

        if status_result.get("status") != 200:
            continue

        files = status_result.get("result", [])

        for file in files:
            if file.get("status") == "finished":
                fileid = file.get("file_id")
                stream_link = f"https://streamtape.com/v/{fileid}"
                await update.message.reply_text(
                    f"✅ Upload selesai!\n\n🔗 {stream_link}"
                )
                return

    await update.message.reply_text("❌ Timeout. Cek dashboard Streamtape.")

# =========================
# HANDLE FILE (DIRECT UPLOAD)
# =========================

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = time.time()

    if user_id in user_cooldowns:
        remaining = COOLDOWN - (now - user_cooldowns[user_id])
        if remaining > 0:
            await update.message.reply_text(f"⏳ Tunggu {int(remaining)} detik.")
            return

    user_cooldowns[user_id] = now

    await update.message.reply_text("⬇️ Download file dari Telegram...")

    file = await update.message.document.get_file()
    filepath = "upload.mp4"
    await file.download_to_drive(filepath)

    await update.message.reply_text("🚀 Upload ke Streamtape...")

    result = upload_file(filepath)

    os.remove(filepath)

    if result.get("status") != 200:
        await update.message.reply_text("❌ Upload gagal.")
        return

    fileid = result["result"]["url"].split("/")[-1]
    stream_link = f"https://streamtape.com/v/{fileid}"

    await update.message.reply_text(
        f"✅ Upload selesai!\n\n🔗 {stream_link}"
    )

# =========================
# RUN
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

print("Streamtape PRO Bot Running...")
app.run_polling()
