import os
import re
import time
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
# Upload via URL
# =========================
def upload_url_to_streamtape(url):
    api = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}&url={url}"
    r = requests.get(api, timeout=60)
    return r.json()

# =========================
# Upload File Direct
# =========================
def upload_file_to_streamtape(filepath):
    api = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    files = {"file1": open(filepath, "rb")}
    r = requests.post(api, files=files, timeout=300)
    return r.json()

# =========================
# Handle Text (URL Upload)
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

    await update.message.reply_text("🚀 Remote upload ke Streamtape...")

    result = upload_url_to_streamtape(urls[0])

    if result.get("status") != 200:
        await update.message.reply_text("❌ Upload gagal.")
        return

    link = result["result"]["url"]

    await update.message.reply_text(f"✅ Upload selesai!\n\n🔗 {link}")

# =========================
# Handle File Upload
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

    result = upload_file_to_streamtape(filepath)

    os.remove(filepath)

    if result.get("status") != 200:
        await update.message.reply_text("❌ Upload gagal.")
        return

    link = result["result"]["url"]

    await update.message.reply_text(f"✅ Upload selesai!\n\n🔗 {link}")

# =========================
# RUN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

print("Streamtape Bot Running...")
app.run_polling()
