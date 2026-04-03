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


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kirim video untuk diupload ke Streamtape (max 2GB).")


# ================= GET UPLOAD SERVER =================
def get_upload_server():
    url = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception("Gagal ambil upload server")

    data = response.json()

    if data.get("status") != 200:
        raise Exception(f"Streamtape API error: {data}")

    return data["result"]["url"]


# ================= HANDLE VIDEO =================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    file = message.video or message.document

    if not file:
        await message.reply_text("File tidak valid.")
        return

    await message.reply_text("Memproses...")

    try:
        # Ambil file info dari Telegram
        telegram_file = await context.bot.get_file(file.file_id)

        # Ini URL langsung dari Telegram (bisa sampai 2GB)
        telegram_file_url = telegram_file.file_path

        upload_url = get_upload_server()

        # Kirim URL langsung ke Streamtape
        data = {
            "url": telegram_file_url
        }

        response = requests.post(upload_url, data=data)

        print("Upload response:", response.text)

        result = response.json()

        if result.get("status") != 200:
            raise Exception(f"Upload gagal: {result}")

        link = result["result"]["url"]

        await message.reply_text(f"Upload berhasil!\n{link}")

    except Exception as e:
        await message.reply_text(f"ERROR: {str(e)}")


# ================= MAIN =================
def main():
    print("=== BOT STARTING (PRO 2GB MODE) ===")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video)
    )

    app.bot.delete_webhook(drop_pending_updates=True)

    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
