
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

load_dotenv()

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = (os.getenv("BOT_TOKEN") or "").strip()
    # ادمین‌های اولیه (دایمی) از .env
    ADMIN_IDS: set[int] = frozenset(
        int(x) for x in (os.getenv("ADMIN_IDS") or "").replace(" ", "").split(",") if x
    )
    # ادمین اصلی (صاحب) – فقط یک نفر
    OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
    TARGET_GROUP_ID: int = int(os.getenv("TARGET_GROUP_ID", "0"))
    PROXY_URL: str = (os.getenv("PROXY_URL") or "").strip()
    # صفحه‌ی فرم عمومی
    WEBAPP_URL: str = (os.getenv("WEBAPP_URL") or "").strip()
    # صفحه‌ی مدیریت (می‌توانی از .env بدهی؛ در غیر این صورت، از کنار index.html => admin.html می‌سازیم)
    ADMIN_WEBAPP_URL: str = (os.getenv("ADMIN_WEBAPP_URL") or "").strip()

SETTINGS = Settings()

# اگر ADMIN_WEBAPP_URL خالی بود، از WEBAPP_URL بساز:
if SETTINGS.WEBAPP_URL and not SETTINGS.ADMIN_WEBAPP_URL:
    if SETTINGS.WEBAPP_URL.endswith("index.html"):
        SETTINGS.ADMIN_WEBAPP_URL = SETTINGS.WEBAPP_URL.replace("index.html", "admin.html")
    else:
        SETTINGS.ADMIN_WEBAPP_URL = SETTINGS.WEBAPP_URL.rsplit("/", 1)[0] + "/admin.html"

def build_bot_and_dispatcher():
    if not SETTINGS.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN در .env تنظیم نشده است.")
    session = AiohttpSession(proxy=SETTINGS.PROXY_URL) if SETTINGS.PROXY_URL else None
    bot = Bot(SETTINGS.BOT_TOKEN, session=session)
    dp = Dispatcher()
    return bot, dp
