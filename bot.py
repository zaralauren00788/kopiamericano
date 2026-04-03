import os
import aiohttp
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
    await update.message.reply_text(
        "Kirim video atau file untuk upload ke Streamtape (max 2GB)."
    )


# ================= GET UPLOAD SERVER =================
async def get_upload_server():
    url = f"https://api.streamtape.com/file/ul?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

            if data.get("status") != 200:
                raise Exception(f"Gagal ambil upload server: {data}")

            return data["result"]["url"]


# ================= HANDLE VIDEO / FILE =================
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

        # URL direct Telegram (bisa sampai 2GB)
        telegram_file_url = telegram_file.file_path

        # Ambil upload server Streamtape
        upload_url = await get_upload_server()

        # Upload via multipart/form-data
        async with aiohttp.ClientSession() as session:

            form = aiohttp.FormData()
            form.add_field("url", telegram_file_url)

            async with session.post(upload_url, data=form) as resp:
                result = await resp.json()

        if result.get("status") != 200:
            raise Exception(f"Upload gagal: {result}")

        link = result["result"]["url"]

        await message.reply_text(f"Upload berhasil!\n{link}")

    except Exception as e:
        await message.reply_text(f"ERROR: {str(e)}")


# ================= MAIN =================
def main():
    print("=== BOT STARTING (2GB PRO MODE) ===")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video)
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
