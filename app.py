import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.get("/")
def home():
    return "Fibo ABU JOD Telegram Webhook is running."

@app.post("/webhook")
def webhook():
    if not BOT_TOKEN or not CHAT_ID:
        return jsonify({"ok": False, "error": "BOT_TOKEN or CHAT_ID is missing"}), 500

    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("text") or ""

    if not message:
        message = request.get_data(as_text=True) or "Empty TradingView alert"

    res = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    return jsonify({
        "ok": res.ok,
        "telegram_status": res.status_code,
        "telegram_response": res.text
    }), 200 if res.ok else 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
