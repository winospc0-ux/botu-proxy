import os
import re
import json
import asyncio
import shutil
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL", "https://api.telegram.org")
COOKIES_FILE = "cookies.txt"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_ydl_opts(extra_opts=None):
    opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    if extra_opts:
        opts.update(extra_opts)
    return opts

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! أرسل رابط يوتيوب لأبدأ.\n"
        "سأعطيك خيارات الدقة للتحميل."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not re.match(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/', url):
        return

    msg = await update.message.reply_text("جاري جلب المعلومات...")

    try:
        with yt_dlp.YoutubeDL(get_ydl_opts({"listformats": True})) as ydl:
            info = ydl.extract_info(url, download=False)

        context.user_data["info"] = {
            "url": url,
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "formats": info.get("formats", []),
        }

        formats = info.get("formats", [])
        keyboard = []
        seen = set()
        for f in formats:
            height = f.get("height")
            ext = f.get("ext", "mp4")
            if height and f.get("vcodec") != "none" and height not in seen:
                seen.add(height)
                label = f"{height}p ({ext})"
                if f.get("filesize"):
                    size_mb = f["filesize"] / 1024 / 1024
                    label += f" {size_mb:.0f}MB"
                keyboard.append([InlineKeyboardButton(label, callback_data=f"dl_{height}_{ext}")])

        keyboard.append([InlineKeyboardButton("🎥 أعلى دقة", callback_data="dl_best")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="dl_cancel")])

        await msg.edit_text(
            f"**{info.get('title', 'فيديو')}**\nاختر الدقة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
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

    ydl_opts = get_ydl_opts({
        "writethumbnail": True,
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
    })

    if data == "dl_best":
        ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        _, height, ext = data.split("_")
        ydl_opts["format"] = f"bestvideo[height<={height}][ext={ext}]+bestaudio[ext=m4a]/best[height<={height}]"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(info["url"], download=True)

        video_id = info_dict["id"]
        ext = info_dict.get("ext", "mp4")
        video_path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        title = info_dict.get("title", "")
        thumb_path = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(video_id) and f != f"{video_id}.{ext}":
                thumb_path = os.path.join(DOWNLOAD_DIR, f)
                break

        caption = f"🎬 {title}"
        with open(video_path, "rb") as vf:
            await query.message.reply_video(
                video=vf,
                caption=caption,
                thumbnail=open(thumb_path, "rb") if thumb_path and os.path.getsize(thumb_path) < 10 * 1024 * 1024 else None,
                supports_streaming=True,
            )

        os.remove(video_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

        await query.delete_message()
    except Exception as e:
        await query.edit_message_text(f"خطأ: {e}")

def main():
    app = Application.builder().token(TOKEN).base_url(f"{TELEGRAM_API_URL}/bot").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
