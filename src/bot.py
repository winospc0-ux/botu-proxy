import os
import re
import json
import asyncio
import logging
import subprocess
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL", "https://api.telegram.org")
COOKIES_FILE = "data/cookies.txt"
DOWNLOAD_DIR = "downloads"
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! أرسل رابط يوتيوب لأبدأ.\nسأعطيك خيارات الدقة للتحميل.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not re.search(r'(youtube\.com|youtu\.be)', url):
        return

    msg = await update.message.reply_text("جاري جلب المعلومات...")

    try:
        with yt_dlp.YoutubeDL({
            "quiet": True, "no_warnings": True,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        }) as ydl:
            info = ydl.extract_info(url, download=False)

        context.user_data["info"] = {"url": url, "title": info.get("title", ""), "thumbnail": info.get("thumbnail", "")}

        formats = info.get("formats", [])
        keyboard = []
        seen = set()
        for f in formats:
            h = f.get("height")
            ext = f.get("ext", "mp4")
            if h and f.get("vcodec") != "none" and h not in seen:
                seen.add(h)
                label = f"{h}p ({ext})"
                if f.get("filesize"):
                    label += f" {f['filesize']/1024/1024:.0f}MB"
                keyboard.append([InlineKeyboardButton(label, callback_data=f"dl_{h}_{ext}")])

        keyboard.append([InlineKeyboardButton("🎥 أعلى دقة", callback_data="dl_best")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="dl_cancel")])

        await msg.edit_text(f"**{info.get('title')}**\nاختر الدقة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"خطأ: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    info = context.user_data.get("info")
    if not info:
        await query.edit_message_text("انتهت الجلسة، أرسل الرابط مجدداً.")
        return

    if data == "dl_cancel":
        await query.edit_message_text("تم الإلغاء.")
        return

    await query.edit_message_text("جاري التحميل والرفع...")

    fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" if data == "dl_best" else f"bestvideo[height<={data.split('_')[1]}][ext={data.split('_')[2]}]+bestaudio[ext=m4a]/best[height<={data.split('_')[1]}]"

    try:
        with yt_dlp.YoutubeDL({
            "format": fmt, "quiet": True, "no_warnings": True,
            "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s", "writethumbnail": True,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        }) as ydl:
            d = ydl.extract_info(info["url"], download=True)

        vid, ext = d["id"], d.get("ext", "mp4")
        vpath = f"{DOWNLOAD_DIR}/{vid}.{ext}"
        tpath = next((f"{DOWNLOAD_DIR}/{f}" for f in os.listdir(DOWNLOAD_DIR) if f.startswith(vid) and f != f"{vid}.{ext}"), None)

        caption = f"🎬 {d.get('title', '')}"
        with open(vpath, "rb") as vf:
            await query.message.reply_video(video=vf, caption=caption, thumbnail=open(tpath, "rb") if tpath and os.path.getsize(tpath) < 10*1024*1024 else None, supports_streaming=True)

        os.remove(vpath)
        if tpath and os.path.exists(tpath):
            os.remove(tpath)
        await query.delete_message()
    except Exception as e:
        await query.edit_message_text(f"خطأ: {e}")

async def test_outbound():
    import httpx
    for url in ["https://api.telegram.org", "https://cloudflare.com", "https://botutu.talaali.workers.dev"]:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(url)
                logging.info(f"✅ {url} -> {r.status_code}")
        except Exception as e:
            logging.error(f"❌ {url} -> {e}")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_outbound())

    app = Application.builder().token(TOKEN).base_url(f"{TELEGRAM_API_URL}/bot").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))

    if WEBHOOK_URL:
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
