import os, re, json, logging, urllib.parse, io, asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import requests

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "data/cookies.txt" if os.path.exists("data/cookies.txt") else None
YT_WORKER = os.getenv("YT_WORKER", "").rstrip("/")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
user_data: dict[int, dict] = {}

def wfetch(url):
    """جب أي URL عبر الـ Worker"""
    if YT_WORKER:
        url = f"{YT_WORKER}/?url={urllib.parse.quote(url)}"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r

def get_video_info(video_url):
    """استخراج معلومات الفيديو من صفحة يوتيوب"""
    html = wfetch(video_url).text
    # استخراج ytInitialPlayerResponse
    m = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
    if not m:
        # محاولة ثانية
        m = re.search(r'window\.ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
    if not m:
        raise Exception("ما لقيت بيانات الفيديو")
    data = json.loads(m.group(1))
    title = data.get("videoDetails", {}).get("title", "بدون عنوان")
    vid = data.get("videoDetails", {}).get("videoId", "")
    thumb = data.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [{}])[-1].get("url", "")

    formats = []
    seen = set()
    for fmt in data.get("streamingData", {}).get("formats", []):
        h = fmt.get("height")
        if h and h not in seen:
            seen.add(h)
            formats.append({
                "height": h,
                "ext": fmt.get("mimeType", "").split("/")[1].split(";")[0],
                "url": fmt.get("url", ""),
                "filesize": fmt.get("contentLength", 0),
            })
    # adaptiveFormats (لها URLs)
    for fmt in data.get("streamingData", {}).get("adaptiveFormats", []):
        h = fmt.get("height")
        if h and h not in seen:
            seen.add(h)
            formats.append({
                "height": h,
                "ext": fmt.get("mimeType", "").split("/")[1].split(";")[0],
                "url": fmt.get("url", ""),
                "filesize": fmt.get("contentLength", 0),
            })
    formats.sort(key=lambda x: x["height"], reverse=True)
    return {"id": vid, "title": title, "thumb": thumb, "formats": formats}

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
        info = await asyncio.get_event_loop().run_in_executor(None, get_video_info, url)
        user_data[message.from_user.id] = info
        keyboard = []
        for f in info["formats"]:
            label = f"{f['height']}p ({f['ext']})"
            if f["filesize"]:
                label += f" {int(f['filesize'])/1024/1024:.0f}MB"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"dl_{f['height']}_{f['ext']}")])
        keyboard.append([InlineKeyboardButton("🎥 أعلى دقة", callback_data="dl_best")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="dl_cancel")])
        await msg.edit_text(f"**{info['title']}**\nاختر الدقة:", reply_markup=InlineKeyboardMarkup(keyboard))
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
    try:
        # اختيار الدقة
        if data == "dl_best":
            chosen = info["formats"][0]  # أول واحد (أعلى دقة)
        else:
            h = int(data.split("_")[1])
            chosen = next((f for f in info["formats"] if f["height"] == h), info["formats"][0])

        if not chosen.get("url"):
            raise Exception("ما فيه رابط تحميل لهذه الدقة")

        # تحميل الفيديو عبر الـ Worker
        vpath = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{chosen['ext']}")
        r = wfetch(chosen["url"])
        with open(vpath, "wb") as f:
            f.write(r.content)

        caption = f"🎬 {info['title']}"
        await callback.message.reply_video(video=vpath, caption=caption, supports_streaming=True)
        os.remove(vpath)
        await callback.message.delete()
    except Exception as e:
        await callback.message.edit_text(f"خطأ: {e}")

# ── Health check server ──
PORT = int(os.getenv("PORT", "7860"))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h1>Bot is running</h1>")
    def log_message(self, fmt, *args):
        pass

Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever(), daemon=True).start()
logging.info(f"🌐 Web server on port {PORT}")

app.run()
