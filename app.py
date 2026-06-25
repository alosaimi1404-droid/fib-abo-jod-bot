import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

CHAT_ID_1 = os.getenv("CHAT_ID_1")
CHAT_ID_2 = os.getenv("CHAT_ID_2")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


@app.get("/")
def home():
    return "Fibo ABU JOD Telegram Webhook is running."


def get_message():
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("text") or ""

    if not message:
        message = request.get_data(as_text=True) or "Empty TradingView alert"

    return message


@app.post("/webhook1")
def webhook1():

    message = get_message()

    res = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": CHAT_ID_1,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    return jsonify({
        "ok": res.ok,
        "response": res.text
    }), 200


@app.post("/webhook2")
def webhook2():

    message = get_message()

    res = requests.post(
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
        "ok": res.ok,
        "response": res.text
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
