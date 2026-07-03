import os
import re
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import yt_dlp

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
COOKIES_FILE = "data/cookies.txt" if os.path.exists("data/cookies.txt") else None
DOWNLOAD_DIR = "downloads"
YT_WORKER = os.getenv("YT_WORKER", "").rstrip("/")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
user_data: dict[int, dict] = {}

def ydl_opts(extra=None):
    opts = {"quiet": True, "no_warnings": True, "cookiefile": COOKIES_FILE}
    if YT_WORKER:
        opts["proxy"] = YT_WORKER
    if extra:
        opts.update(extra)
    return opts

app = Client("yt_dl_bot", bot_token=TOKEN, api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("مرحباً! أرسل رابط يوتيوب لأبدأ.\nسأعطيك خيارات الدقة للتحميل.")

@app.on_message(filters.text & ~filters.command(""))
async def handle_url(client, message):
    url = message.text.strip()
    if not re.search(r'(youtube\.com|youtu\.be)', url):
        return
    msg = await message.reply("جاري جلب المعلومات...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        user_data[message.from_user.id] = {"url": url, "title": info.get("title", "")}
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
        await msg.edit_text(f"**{info.get('title')}**\nاختر الدقة:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg.edit_text(f"خطأ: {e}")

@app.on_callback_query()
async def button_handler(client, callback: CallbackQuery):
    data = callback.data
    uid = callback.from_user.id
    info = user_data.get(uid)
    if not info:
        await callback.message.edit_text("انتهت الجلسة، أرسل الرابط مجدداً.")
        return
    if data == "dl_cancel":
        await callback.message.edit_text("تم الإلغاء.")
        return
    await callback.message.edit_text("جاري التحميل والرفع...")
    fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" if data == "dl_best" else f"bestvideo[height<={data.split('_')[1]}][ext={data.split('_')[2]}]+bestaudio[ext=m4a]/best[height<={data.split('_')[1]}]"
    try:
        with yt_dlp.YoutubeDL(ydl_opts({"format": fmt, "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s", "writethumbnail": True})) as ydl:
            d = ydl.extract_info(info["url"], download=True)
        vid, ext = d["id"], d.get("ext", "mp4")
        vpath = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
        tpath = next((os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.startswith(vid) and f != f"{vid}.{ext}"), None)
        caption = f"🎬 {d.get('title', '')}"
        thumb = open(tpath, "rb") if tpath and os.path.getsize(tpath) < 10*1024*1024 else None
        await callback.message.reply_video(video=vpath, caption=caption, thumb=thumb, supports_streaming=True)
        if thumb:
            thumb.close()
        os.remove(vpath)
        if tpath and os.path.exists(tpath):
            os.remove(tpath)
        await callback.message.delete()
    except Exception as e:
        await callback.message.edit_text(f"خطأ: {e}")

app.run()
