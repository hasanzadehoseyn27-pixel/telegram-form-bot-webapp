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

# از ENV
APP_BASE_URL = (os.getenv("APP_BASE_URL") or "").rstrip("/")  # مثل: https://your-domain.com
WEBHOOK_PATH = f"/webhook/{SETTINGS.BOT_TOKEN}"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

async def main():
    bot, dp = build_bot_and_dispatcher()
    dp.include_router(router)

    app = web.Application()

    # یک روت ساده برای سلامت/آزمایش
    async def ping(_):
        return web.Response(text="OK", status=200)
    app.router.add_get("/", ping)

    # ثبت هندلر وبهوک
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    # on_startup / on_shutdown برای setWebhook/deleteWebhook
    async def _on_startup(_app: web.Application):
        if not APP_BASE_URL:
            logger.warning("APP_BASE_URL خالی است؛ وبهوک را دستی با BotFather ست کنید.")
            return
        url = f"{APP_BASE_URL}{WEBHOOK_PATH}"
        try:
            await bot.set_webhook(url, drop_pending_updates=True)
            logger.info("Webhook set to %s", url)
        except Exception as e:
            # اگر خروجی شبکه بسته است، اینجا خطا می‌گیری؛ مشکلی نیست، بعداً با BotFather ست کن.
            logger.warning("Cannot set webhook automatically: %s", e)

    async def _on_shutdown(_app: web.Application):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass

    setup_application(app, dp, bot=bot, on_startup=[_on_startup], on_shutdown=[_on_shutdown])

    # ✅ به‌جای web.run_app از AppRunner/TCPSite استفاده می‌کنیم
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=HOST, port=PORT)
    await site.start()

    logger.info("HTTP server started on %s:%s", HOST, PORT)
    logger.info("Webhook path: %s", WEBHOOK_PATH)
    if APP_BASE_URL:
        logger.info("Expected full webhook URL: %s%s", APP_BASE_URL, WEBHOOK_PATH)
    else:
        logger.info("APP_BASE_URL تعیین نشده؛ وبهوک را با BotFather ست کنید.")

    # نگه‌داشتن برنامه
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
