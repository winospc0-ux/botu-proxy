import os, re, json, logging, urllib.parse, asyncio, subprocess
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
NETLIFY_PROXY = os.getenv("NETLIFY_PROXY", "").rstrip("/")
COOKIES_FILE = "data/cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
user_data: dict[int, dict] = {}



_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def _load_cookies():
    if not os.path.exists(COOKIES_FILE):
        return {}
    jar = {}
    with open(COOKIES_FILE) as f:
        raw = f.read().strip()
    # JSON format
    if raw.startswith("["):
        try:
            for c in json.loads(raw):
                if c.get("name") and c.get("value"):
                    jar[c["name"]] = c["value"]
            return jar
        except:
            pass
    # Netscape format
    for line in raw.split("\n"):
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            jar[parts[5]] = parts[6]
    return jar

def _save_cookies(raw):
    """حفظ الكوكيز بأي صيغة (JSON أو Netscape)"""
    raw = raw.strip()
    # JSON → Netscape
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            lines = []
            for c in data:
                domain = c.get("domain", "")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure") else "FALSE"
                expiry = str(int(c.get("expirationDate", 0)))
                name = c.get("name", "")
                value = c.get("value", "")
                lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
            with open(COOKIES_FILE, "w") as f:
                f.write("\n".join(lines))
            return len(lines)
        except:
            pass
    # Netscape format as-is
    with open(COOKIES_FILE, "w") as f:
        f.write(raw)
    return len([l for l in raw.split("\n") if l.strip() and not l.startswith("#")])

def fetch(url, timeout=30):
    """Fetch via Netlify proxy فقط"""
    cookies = _load_cookies()
    hdrs = dict(_headers)
    if cookies:
        hdrs["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    if not NETLIFY_PROXY:
        raise Exception("NETLIFY_PROXY غير مضبوط في الإعدادات")
    wurl = f"{NETLIFY_PROXY}?url={urllib.parse.quote(url)}"
    r = requests.get(wurl, headers=hdrs, timeout=timeout)
    r.raise_for_status()
    return r

def ytdlp_get_url(video_url):
    """Get actual download URL using yt-dlp (handles signature decryption)"""
    cmd = ["yt-dlp", "-g", "--no-warnings", "-f", "best"]
    if os.path.exists(COOKIES_FILE):
        cmd += ["--cookies", COOKIES_FILE]
    r = subprocess.run(cmd + [video_url], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise Exception(f"yt-dlp: {r.stderr.strip()}")
    return r.stdout.strip().split("\n")[0]

def get_video_info(video_url):
    try:
        html = fetch(video_url).text
    except Exception as e:
        raise Exception(f"فشل جلب الصفحة: {e}")
    if "captcha" in html.lower() or "solveSimpleChallenge" in html:
        raise Exception("يوتيوب طلب CAPTCHA. جرب:\n1. حدّث الكوكيز (data/cookies.txt)\n2. أو أرسل /test عشان نشوف الاتصال")
    m = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
    if not m:
        m = re.search(r'window\.ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
    if not m:
        raise Exception("ما لقيت بيانات الفيديو في الصفحة")
    data = json.loads(m.group(1))
    title = data.get("videoDetails", {}).get("title", "بدون عنوان")
    vid = data.get("videoDetails", {}).get("videoId", "")
    streaming = data.get("streamingData", {})
    formats = []
    seen = set()
    for src in ("formats", "adaptiveFormats"):
        for fmt in streaming.get(src, []):
            h = fmt.get("height")
            if h and h not in seen:
                seen.add(h)
                url = fmt.get("url") or ""
                if not url and "cipher" in fmt:
                    from urllib.parse import parse_qs
                    q = parse_qs(fmt["cipher"])
                    url = q.get("url", [""])[0]
                formats.append({
                    "height": h,
                    "ext": fmt.get("mimeType", "").split("/")[1].split(";")[0],
                    "filesize": fmt.get("contentLength", 0) and int(fmt["contentLength"]),
                    "url": url,
                })
    formats.sort(key=lambda x: x["height"], reverse=True)
    return {"id": vid, "title": title, "formats": formats}

app = Client("yt_dl_bot", bot_token=TOKEN, api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("مرحباً! أرسل رابط يوتيوب لأبدأ.\nسأعطيك خيارات الدقة للتحميل.\n/cookies لإدارة كوكيز يوتيوب.")

@app.on_message(filters.command("cookies"))
async def cookies_cmd(client, message):
    if not os.path.exists(COOKIES_FILE):
        await message.reply("❌ ملف الكوكيز غير موجود.\nأرسل ملف cookies.txt أو الصق محتواه رداً على هذه الرسالة.")
        return
    with open(COOKIES_FILE) as f:
        content = f.read().strip()
    # Detect format
    if content.startswith("["):
        try:
            data = json.loads(content)
            count = len(data)
            expiry_dates = []
            for c in data:
                if c.get("expirationDate"):
                    import datetime
                    expiry_dates.append(f"  • {c['name']}: {datetime.datetime.fromtimestamp(c['expirationDate']).strftime('%Y-%m-%d %H:%M')}")
            info = f"📋 **الكوكيز:** {count} كوكي (JSON)\n"
            if expiry_dates:
                info += "⏳ **الصلاحية:**\n" + "\n".join(expiry_dates[:10])
                if len(expiry_dates) > 10:
                    info += f"\n  ... و{len(expiry_dates)-10} أخرى"
        except:
            info = "⚠️ ملف الكوكيز بتنسيق غير معروف"
    else:
        lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
        expiry_dates = []
        for l in lines:
            parts = l.split("\t")
            if len(parts) >= 7 and parts[4] != "0":
                import datetime
                dt = datetime.datetime.fromtimestamp(int(parts[4]))
                expiry_dates.append(f"  • {parts[5]}: {dt.strftime('%Y-%m-%d %H:%M')}")
        info = f"📋 **الكوكيز:** {len(lines)} كوكي (Netscape)\n"
        if expiry_dates:
            info += "⏳ **الصلاحية:**\n" + "\n".join(expiry_dates[:10])
            if len(expiry_dates) > 10:
                info += f"\n  ... و{len(expiry_dates)-10} أخرى"
    info += "\n\n**للتحديث:** أرسل ملف cookies.txt أو الصق المحتوى رداً على هذه الرسالة"
    await message.reply(info + "\n\n(/cookies)")

@app.on_message(filters.document & filters.reply)
async def handle_cookies_file(client, message):
    reply_to = message.reply_to_message
    if not reply_to or not reply_to.text or "/cookies" not in reply_to.text:
        return
    msg = await message.reply("جاري حفظ الكوكيز...")
    try:
        path = await message.download()
        with open(path) as f:
            content = f.read()
        os.remove(path)
        count = _save_cookies(content)
        await msg.edit_text(f"✅ تم حفظ {count} كوكيز!")
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")

@app.on_message(filters.text & filters.reply & ~filters.command(""))
async def handle_cookies_text(client, message):
    reply_to = message.reply_to_message
    if not reply_to or not reply_to.text or "/cookies" not in reply_to.text:
        return
    try:
        count = _save_cookies(message.text)
        await message.reply(f"✅ تم حفظ {count} كوكيز!")
    except Exception as e:
        await message.reply(f"❌ خطأ: {e}")

@app.on_message(filters.text & ~filters.command(""))
async def handle_url(client, message):
    url = message.text.strip()
    if not re.search(r'(youtube\.com|youtu\.be)', url):
        return
    msg = await message.reply("جاري جلب المعلومات...")
    try:
        loop = asyncio.get_event_loop()
        info = await asyncio.wait_for(
            loop.run_in_executor(None, get_video_info, url),
            timeout=90
        )
        user_data[message.from_user.id] = info
        keyboard = []
        for f in info["formats"]:
            label = f"{f['height']}p ({f['ext']})"
            if f["filesize"]:
                label += f" {f['filesize']/1024/1024:.0f}MB"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"dl_{f['height']}_{f['ext']}")])
        keyboard.append([InlineKeyboardButton("🎥 أعلى دقة", callback_data="dl_best")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="dl_cancel")])
        await msg.edit_text(f"**{info['title']}**\nاختر الدقة:", reply_markup=InlineKeyboardMarkup(keyboard))
    except asyncio.TimeoutError:
        await msg.edit_text("خطأ: انتهت المهلة (35 ثانية)")
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
        chosen = info["formats"][0] if data == "dl_best" else next((f for f in info["formats"] if f["height"] == int(data.split("_")[1])), info["formats"][0])
        durl = chosen.get("url")
        ext = chosen["ext"]
        vpath = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{ext}")
        if not durl:
            raise Exception("ما فيه رابط تحميل مباشر")
        loop = asyncio.get_event_loop()
        r = await asyncio.wait_for(
            loop.run_in_executor(None, fetch, durl),
            timeout=60
        )
        with open(vpath, "wb") as f:
            f.write(r.content)
        await callback.message.reply_video(video=vpath, caption=f"🎬 {info['title']}", supports_streaming=True)
        os.remove(vpath)
        await callback.message.delete()
    except asyncio.TimeoutError:
        await callback.message.edit_text("خطأ: انتهت المهلة أثناء التحميل")
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

# تشغيل البوت مع إعادة محاولة إذا صار FloodWait
import time
for attempt in range(10):
    try:
        app.run()
        break
    except KeyboardInterrupt:
        raise
    except Exception as e:
        msg = str(e)
        if "FLOOD_WAIT" in msg:
            import re
            m = re.search(r"(\d+)", msg)
            secs = int(m.group(1)) + 5 if m else 120
            logging.warning(f"⚠️ FloodWait, انتظار {secs}ث...")
            time.sleep(secs)
        else:
            logging.error(f"❌ خطأ: {e}")
            time.sleep(10)
