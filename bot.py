import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =============================
# ENV VARIABLES
# =============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan di environment!")

# =============================
# COMMANDS
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif 🚀")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"User ID kamu: {update.effective_user.id}")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Kamu bukan admin.")
        return

    await update.message.reply_text("Halo Admin 👑")

# =============================
# MAIN FUNCTION
# =============================

def main():
    print("=== BOT STARTING ===")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("admin", admin))

    print("=== RUNNING POLLING ===")

    application.run_polling(
        drop_pending_updates=True,
        close_loop=False
    )

# =============================
# ENTRY POINT
# =============================

if __name__ == "__main__":
    main()
