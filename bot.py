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


# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kirim video untuk diupload ke Streamtape.")


# ================= GET UPLOAD SERVER =================
def get_upload_server():
    url = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    response = requests.get(url)

    print("Upload server status:", response.status_code)
    print("Upload server response:", response.text)

    if response.status_code != 200:
        raise Exception("Gagal ambil upload server")

    try:
        data = response.json()
    except:
        raise Exception("Response bukan JSON (cek login/key Streamtape)")

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

    await message.reply_text("Downloading file...")

    telegram_file = await context.bot.get_file(file.file_id)
    file_path = "video_upload"

    await telegram_file.download_to_drive(file_path)

    await message.reply_text("Uploading ke Streamtape...")

    try:
        upload_url = get_upload_server()

        with open(file_path, "rb") as f:
            files = {"file1": f}
            response = requests.post(upload_url, files=files)

        print("Upload status:", response.status_code)
        print("Upload response:", response.text)

        try:
            data = response.json()
        except:
            raise Exception("Upload response bukan JSON")

        if data.get("status") != 200:
            raise Exception(f"Upload gagal: {data}")

        result = data["result"]
        link = result.get("url")

        await message.reply_text(f"Upload berhasil!\n{link}")

    except Exception as e:
        await message.reply_text(f"ERROR: {str(e)}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# ================= MAIN =================
def main():
    print("=== BOT STARTING ===")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video)
    )

    print("Clearing old webhook...")

    # Anti conflict polling
    app.bot.delete_webhook(drop_pending_updates=True)

    print("=== RUNNING POLLING ===")

    app.run_polling(
        drop_pending_updates=True,
        close_loop=False,
    )


if __name__ == "__main__":
    main()
