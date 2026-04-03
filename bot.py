import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
STREAMTAPE_LOGIN = os.getenv("STREAMTAPE_LOGIN")
STREAMTAPE_KEY = os.getenv("STREAMTAPE_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan!")

if not STREAMTAPE_LOGIN or not STREAMTAPE_KEY:
    raise ValueError("STREAMTAPE_LOGIN / STREAMTAPE_KEY belum di-set!")

# =========================
# COMMAND
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kirim video untuk upload ke Streamtape 🚀")

# =========================
# UPLOAD HANDLER
# =========================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("Downloading file...")

        file = None

        if update.message.video:
            file = await update.message.video.get_file()
            filename = update.message.video.file_name or "video.mp4"
        elif update.message.document:
            file = await update.message.document.get_file()
            filename = update.message.document.file_name or "file.mp4"
        else:
            await update.message.reply_text("Kirim video atau file ya.")
            return

        filepath = f"/tmp/{filename}"

        # Download ke disk (bukan RAM)
        await file.download_to_drive(filepath)

        await update.message.reply_text("Uploading ke Streamtape...")

        # Step 1: Ambil upload server
        server_res = requests.get(
            "https://api.streamtape.com/file/ul",
            params={
                "login": STREAMTAPE_LOGIN,
                "key": STREAMTAPE_KEY,
            },
        ).json()

        if server_res["status"] != 200:
            await update.message.reply_text("Gagal ambil server upload.")
            return

        upload_url = server_res["result"]["url"]

        # Step 2: Upload file
        with open(filepath, "rb") as f:
            upload_res = requests.post(
                upload_url,
                files={"file1": f},
                data={
                    "login": STREAMTAPE_LOGIN,
                    "key": STREAMTAPE_KEY,
                },
            ).json()

        if upload_res["status"] != 200:
            await update.message.reply_text("Upload gagal.")
            return

        link = upload_res["result"]["url"]

        await update.message.reply_text(f"Upload berhasil ✅\n\n{link}")

        # Hapus file lokal
        os.remove(filepath)

    except Exception as e:
        print("ERROR:", e)
        await update.message.reply_text(f"Terjadi error:\n{e}")

# =========================
# MAIN
# =========================

def main():
    print("=== BOT STARTING ===")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))

    print("=== RUNNING POLLING ===")

    app.run_polling(
        drop_pending_updates=True,
        close_loop=False,
    )

if __name__ == "__main__":
    main()
