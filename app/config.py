import os
from dataclasses import dataclass
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

load_dotenv()

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = (os.getenv("BOT_TOKEN") or "").strip()
    OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))  # ادمین اصلی
    ADMIN_IDS: set[int] = frozenset(
        int(x) for x in (os.getenv("ADMIN_IDS") or "").replace(" ", "").split(",") if x
    )
    TARGET_GROUP_ID: int = int(os.getenv("TARGET_GROUP_ID", "0"))
    PROXY_URL: str = (os.getenv("PROXY_URL") or "").strip()
    WEBAPP_URL: str = (os.getenv("WEBAPP_URL") or "").strip()

SETTINGS = Settings()

def build_bot_and_dispatcher():
    if not SETTINGS.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN در .env تنظیم نشده است.")
    session = AiohttpSession(proxy=SETTINGS.PROXY_URL) if SETTINGS.PROXY_URL else None
    bot = Bot(SETTINGS.BOT_TOKEN)  # parse_mode را به اینجا پاس نمی‌دهیم
    bot.session = session or bot.session
    dp = Dispatcher()
    return bot, dp
