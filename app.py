import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

CHAT_ID_1 = "-1003967291753"
CHAT_ID_2 = "-1004452443322"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.get("/")
def home():
    return "Fibo ABU JOD Telegram Webhook is running."

@app.post("/webhook")
def webhook():

    if not BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "BOT_TOKEN is missing"
        }), 500

    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("text") or ""

    if not message:
        message = request.get_data(as_text=True) or "Empty TradingView alert"

    res1 = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": CHAT_ID_1,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    res2 = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": CHAT_ID_2,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    return jsonify({
        "ok": res1.ok and res2.ok
    }), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
