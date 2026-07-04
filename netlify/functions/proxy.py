import json, urllib.request, urllib.parse, os

def handler(event, context):
    params = event.get("queryStringParameters") or {}
    target = params.get("url", "")
    if not target:
        return {"statusCode": 400, "body": "?url= مطلوب"}

    try:
        req = urllib.request.Request(
            target,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
            }
        )
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read()

        return {
            "statusCode": resp.status,
            "headers": {
                "Content-Type": resp.headers.get("Content-Type", "text/plain"),
            },
            "body": body.decode("utf-8", errors="replace"),
        }
    except Exception as e:
        return {"statusCode": 500, "body": f"Proxy error: {e}"}
