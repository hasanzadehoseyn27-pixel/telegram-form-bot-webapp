# main.py
import os
import asyncio
import logging
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config import build_bot_and_dispatcher, SETTINGS
from app.handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# از ENV بخوان
APP_BASE_URL = (os.getenv("APP_BASE_URL") or "").rstrip("/")
WEBHOOK_PATH = f"/webhook/{SETTINGS.BOT_TOKEN}"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

async def on_startup(bot):
    """
    تلاش برای setWebhook (اگر APP_BASE_URL داده شده باشد).
    اگر شبکه خروجی بسته است، خطا لاگ می‌شود اما سرویس وبهوک بالا می‌آید
    تا بتوانی webhook را از طریق BotFather ست کنی.
    """
    if APP_BASE_URL:
        url = f"{APP_BASE_URL}{WEBHOOK_PATH}"
        try:
            await bot.set_webhook(url, drop_pending_updates=True)
            logger.info("Webhook set to %s", url)
        except Exception as e:
            logger.warning("Cannot set webhook automatically: %s", e)

async def on_shutdown(bot):
    # اگر دسترسی خروجی داری، می‌توانی وبهوک را پاک کنی؛ در غیر این صورت بی‌خیال
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

async def main():
    bot, dp = build_bot_and_dispatcher()
    dp.include_router(router)

    # فقط وبهوک؛ Polling را اصلاً اجرا نمی‌کنیم
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot, on_startup=[on_startup], on_shutdown=[on_shutdown])

    logger.info("HTTP server starting on %s:%s", HOST, PORT)
    web.run_app(app, host=HOST, port=PORT)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
