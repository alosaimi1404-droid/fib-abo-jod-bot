import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor

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

CHART_URL = os.getenv(
    "CHART_URL",
    "https://ar.tradingview.com/chart/J9HYuv1U/?symbol=CAPITALCOM%3AXAUUSD",
)
SCREENSHOT_WAIT_MS = int(os.getenv("SCREENSHOT_WAIT_MS", "9000"))
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# يعيد الـ Webhook الرد فورًا، ثم ينفذ التصوير والإرسال في الخلفية.
executor = ThreadPoolExecutor(max_workers=2)


@app.get("/")
def home():
    return "Fibo ABU JOD Telegram Webhook with chart screenshot is running."


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


def get_message() -> str:
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("text") or ""

    if not message:
        message = request.get_data(as_text=True) or "Empty TradingView alert"

    return str(message)


def capture_chart() -> bytes:
    """Open TradingView in headless Chromium and return a PNG screenshot."""
    logger.info("Opening TradingView chart")

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
                CHART_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            # أعطِ الرسم والمؤشر وقتًا كافيًا للتحميل.
            page.wait_for_timeout(SCREENSHOT_WAIT_MS)

            # محاولة إغلاق نوافذ الموافقة أو الإعلانات إن ظهرت.
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

            # لقطة ثابتة وواضحة للشاشة الحالية.
            image = page.screenshot(
                type="png",
                full_page=False,
                animations="disabled",
            )
            logger.info("Chart screenshot captured")
            return image
        finally:
            browser.close()


def telegram_post(method: str, *, data=None, files=None, timeout=40):
    url = f"{TELEGRAM_API}/{method}"
    response = requests.post(url, data=data, files=files, timeout=timeout)
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
        # إذا احتوت الرسالة على HTML غير صالح، أرسلها كنص عادي.
        payload.pop("parse_mode", None)
        telegram_post("sendMessage", data=payload, timeout=25)


def send_photo(chat_id: str, message: str, image: bytes) -> None:
    # حد Telegram لوصف الصورة هو 1024 حرفًا.
    caption = message[:1024]
    remainder = message[1024:]

    payload = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    files = {
        "photo": ("tradingview-chart.png", io.BytesIO(image), "image/png"),
    }

    try:
        telegram_post("sendPhoto", data=payload, files=files, timeout=50)
    except requests.RequestException:
        # إعادة المحاولة من دون HTML.
        payload.pop("parse_mode", None)
        files = {
            "photo": ("tradingview-chart.png", io.BytesIO(image), "image/png"),
        }
        telegram_post("sendPhoto", data=payload, files=files, timeout=50)

    if remainder:
        send_text(chat_id, remainder)


def process_alert(chat_id: str, message: str) -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing")
        return

    if not chat_id:
        logger.error("Chat ID is missing")
        return

    try:
        image = capture_chart()
        send_photo(chat_id, message, image)
        logger.info("Photo alert sent to chat %s", chat_id)
    except Exception:
        logger.exception("Screenshot failed; sending text alert instead")
        try:
            send_text(chat_id, message)
        except Exception:
            logger.exception("Text fallback also failed")


def queue_alert(chat_id: str, message: str):
    executor.submit(process_alert, chat_id, message)
    return jsonify({"ok": True, "queued": True}), 200


@app.post("/webhook1")
def webhook1():
    return queue_alert(CHAT_ID_1, get_message())


@app.post("/webhook2")
def webhook2():
    return queue_alert(CHAT_ID_2, get_message())


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
