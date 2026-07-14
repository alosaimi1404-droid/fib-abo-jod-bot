import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID_1 = os.getenv("CHAT_ID_1")
CHAT_ID_2 = os.getenv("CHAT_ID_2")

# رابط تخطيط TradingView فقط، بدون symbol.
CHART_BASE_URL = os.getenv(
    "CHART_BASE_URL",
    "https://ar.tradingview.com/chart/J9HYuv1U/",
)

SCREENSHOT_WAIT_MS = int(os.getenv("SCREENSHOT_WAIT_MS", "9000"))
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
executor = ThreadPoolExecutor(max_workers=2)


@app.get("/")
def home():
    return "Fibo ABU JOD dynamic TradingView screenshot webhook is running."


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


def get_alert_data():
    """
    يقبل JSON بالشكل:
    {
      "message": "...",
      "symbol": "CAPITALCOM:XAUUSD",
      "interval": "5"
    }

    وإذا وصل نص عادي، يرسله كما هو ويستخدم الذهب كخيار احتياطي.
    """
    data = request.get_json(silent=True)

    if isinstance(data, dict):
        message = str(data.get("message") or data.get("text") or "")
        symbol = str(data.get("symbol") or "CAPITALCOM:XAUUSD")
        interval = str(data.get("interval") or "5")
        return message or "Empty TradingView alert", symbol, interval

    raw = request.get_data(as_text=True) or "Empty TradingView alert"
    return raw, "CAPITALCOM:XAUUSD", "5"


def build_chart_url(symbol: str, interval: str) -> str:
    query = urlencode({
        "symbol": symbol,
        "interval": interval,
    })
    return f"{CHART_BASE_URL.rstrip('/')}/?{query}"


def capture_chart(symbol: str, interval: str) -> bytes:
    chart_url = build_chart_url(symbol, interval)
    logger.info("Opening chart: %s", chart_url)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        try:
            page = browser.new_page(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
                locale="ar-SA",
            )

            page.goto(
                chart_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            page.wait_for_timeout(SCREENSHOT_WAIT_MS)

            possible_buttons = [
                "button:has-text('Accept all')",
                "button:has-text('Accept')",
                "button:has-text('موافقة')",
                "button:has-text('قبول الكل')",
                "button[aria-label='Close']",
                "button[aria-label='إغلاق']",
            ]

            for selector in possible_buttons:
                try:
                    locator = page.locator(selector).first
                    if locator.is_visible(timeout=500):
                        locator.click(timeout=1000)
                except Exception:
                    pass

            return page.screenshot(
                type="png",
                full_page=False,
                animations="disabled",
            )
        finally:
            browser.close()


def telegram_post(method: str, *, data=None, files=None, timeout=40):
    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        data=data,
        files=files,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def send_text(chat_id: str, message: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }

    try:
        telegram_post("sendMessage", data=payload, timeout=25)
    except requests.RequestException:
        payload.pop("parse_mode", None)
        telegram_post("sendMessage", data=payload, timeout=25)


def send_photo(chat_id: str, message: str, image: bytes) -> None:
    caption = message[:1024]
    remainder = message[1024:]

    payload = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }

    try:
        telegram_post(
            "sendPhoto",
            data=payload,
            files={"photo": ("chart.png", io.BytesIO(image), "image/png")},
            timeout=50,
        )
    except requests.RequestException:
        payload.pop("parse_mode", None)
        telegram_post(
            "sendPhoto",
            data=payload,
            files={"photo": ("chart.png", io.BytesIO(image), "image/png")},
            timeout=50,
        )

    if remainder:
        send_text(chat_id, remainder)


def process_alert(chat_id: str, message: str, symbol: str, interval: str) -> None:
    if not BOT_TOKEN or not chat_id:
        logger.error("BOT_TOKEN or chat ID is missing")
        return

    try:
        image = capture_chart(symbol, interval)
        send_photo(chat_id, message, image)
        logger.info("Photo sent: %s %s", symbol, interval)
    except Exception:
        logger.exception("Screenshot failed; sending text instead")
        try:
            send_text(chat_id, message)
        except Exception:
            logger.exception("Text fallback failed")


def queue_alert(chat_id: str):
    message, symbol, interval = get_alert_data()
    executor.submit(process_alert, chat_id, message, symbol, interval)
    return jsonify({
        "ok": True,
        "queued": True,
        "symbol": symbol,
        "interval": interval,
    }), 200


@app.post("/webhook1")
def webhook1():
    return queue_alert(CHAT_ID_1)


@app.post("/webhook2")
def webhook2():
    return queue_alert(CHAT_ID_2)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
