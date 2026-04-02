import os
import re
import time
import asyncio
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")

# Streamtape
STREAMTAPE_LOGIN = os.getenv("STREAMTAPE_LOGIN")
STREAMTAPE_KEY = os.getenv("STREAMTAPE_KEY")

# Dood
DOOD_API_KEY = os.getenv("DOOD_API_KEY")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", 3))
PER_USER_LIMIT = 20
COOLDOWN = 5
MAX_RETRY = 2

# ================= GLOBAL STATE =================

queue = asyncio.Queue()
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

user_cooldowns = {}
user_queue_count = defaultdict(int)
banned_users = set()

stats = {
    "processed": 0,
    "failed": 0,
    "start_time": time.time()
}

# ================= HOST DETECTOR =================

def detect_host(url):
    if "streamtape.com" in url:
        return "streamtape"
    if "dood." in url or "doodstream" in url:
        return "dood"
    return "streamtape"  # default fallback

# ================= STREAMTAPE =================

def streamtape_remote_add(url):
    api = f"https://api.streamtape.com/remotedl/add?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}&url={url}"
    return requests.get(api, timeout=60).json()

def streamtape_status():
    api = f"https://api.streamtape.com/remotedl/status?login={STREAMTAPE_LOGIN}&key={STREAMTAPE_KEY}"
    return requests.get(api, timeout=60).json()

# ================= DOOD =================

def dood_remote_add(url):
    api = f"https://doodapi.com/api/upload/url?key={DOOD_API_KEY}&url={url}"
    return requests.get(api, timeout=60).json()

# ================= WORKER =================

async def worker(app):
    while True:
        chat_id, user_id, url, retry = await queue.get()

        async with semaphore:
            try:
                host = detect_host(url)

                await app.bot.send_message(chat_id, f"🚀 Processing ({host})")

                if host == "streamtape":
                    result = streamtape_remote_add(url)
                    if result.get("status") != 200:
                        raise Exception("Streamtape add failed")

                    finished = False
                    for _ in range(30):
                        await asyncio.sleep(10)
                        status = streamtape_status()
                        if status.get("status") != 200:
                            continue
                        for f in status.get("result", []):
                            if f.get("status") == "finished":
                                link = f"https://streamtape.com/v/{f.get('file_id')}"
                                await app.bot.send_message(chat_id, f"✅ Done\n🔗 {link}")
                                finished = True
                                break
                        if finished:
                            break
                    if not finished:
                        raise Exception("Timeout")

                elif host == "dood":
                    result = dood_remote_add(url)
                    if result.get("status") != 200:
                        raise Exception("Dood add failed")

                    filecode = result["result"][0]["filecode"]
                    link = f"https://dood.stream/d/{filecode}"
                    await app.bot.send_message(chat_id, f"✅ Uploaded\n🔗 {link}")

                stats["processed"] += 1

            except Exception:
                if retry < MAX_RETRY:
                    await queue.put((chat_id, user_id, url, retry + 1))
                else:
                    await app.bot.send_message(chat_id, f"❌ Failed:\n{url}")
                    stats["failed"] += 1

            user_queue_count[user_id] -= 1
            queue.task_done()

# ================= MESSAGE HANDLER =================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    if user_id in banned_users:
        return

    now = time.time()
    if user_id in user_cooldowns:
        if now - user_cooldowns[user_id] < COOLDOWN:
            return

    user_cooldowns[user_id] = now

    urls = re.findall(r'(https?://[^\s]+)', update.message.text)
    if not urls:
        return

    if user_queue_count[user_id] + len(urls) > PER_USER_LIMIT:
        await update.message.reply_text("❌ Limit antrian tercapai.")
        return

    for url in urls:
        await queue.put((chat_id, user_id, url, 0))
        user_queue_count[user_id] += 1

    await update.message.reply_text(
        f"📦 {len(urls)} link masuk queue\n⚡ Parallel: {MAX_CONCURRENT}"
    )

# ================= ADMIN =================

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = int(time.time() - stats["start_time"])
    await update.message.reply_text(
        f"📊 Stats\n"
        f"Processed: {stats['processed']}\n"
        f"Failed: {stats['failed']}\n"
        f"In Queue: {queue.qsize()}\n"
        f"Uptime: {uptime}s"
    )

# ================= MAIN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CommandHandler("stats", stats_cmd))

async def start_workers(app):
    for _ in range(MAX_CONCURRENT):
        asyncio.create_task(worker(app))

app.post_init = start_workers

print("🔥 Multi-Host PRO Bot Running...")
app.run_polling()
