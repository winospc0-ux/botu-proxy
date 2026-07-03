---
title: YouTube Download Bot
emoji: 🎥
colorFrom: blue
colorTo: red
sdk: docker
pinned: false
---

# YouTube Downloader Bot

بوت تيليجرام لتحميل فيديوهات يوتيوب.

## المتغيرات المطلوبة (Secrets)

- `BOT_TOKEN` - توكن البوت من @BotFather
- `API_ID` - API ID من my.telegram.org
- `API_HASH` - API Hash من my.telegram.org
- `TELEGRAM_API_URL` - (اختياري) رابط وكيل Cloudflare Worker

## إعداد Cloudflare Worker (للتشغيل على HF Spaces)

لأن HF Spaces يحظر الاتصالات الخارجية، استخدم Cloudflare Worker كوسيط:

1. اذهب إلى [Cloudflare Workers](https://workers.cloudflare.com/)
2. أنشئ Worker جديد والصق الكود من `cloudflare-worker.js`
3. انشر الـ Worker واحصل على الرابط (مثل `https://bot-proxy.your-name.workers.dev`)
4. أضف الرابط كقيمة `TELEGRAM_API_URL` في Secrets
