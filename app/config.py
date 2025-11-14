import os
from dataclasses import dataclass
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

load_dotenv()

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = (os.getenv("BOT_TOKEN") or "").strip()
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
    bot = Bot(SETTINGS.BOT_TOKEN, session=session, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    return bot, dp
