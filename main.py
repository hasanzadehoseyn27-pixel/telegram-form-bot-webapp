import asyncio
import os
from aiohttp import web

from app.config import build_bot_and_dispatcher
from app.handlers import router as root_router   # ← حتماً این نام را نگه دارید

async def main():
    bot, dp = build_bot_and_dispatcher()
    dp.include_router(root_router)               # ← و این‌جا همین متغیر

    # ------------------------------------------------------------------ #
    asyncio.create_task(dp.start_polling(bot))

    async def healthcheck(_):
        return web.Response(text="Bot is running!")

    app = web.Application()
    app.router.add_get("/", healthcheck)

    port = int(os.environ.get("PORT", 8080))
    print(f"HTTP server started on 0.0.0.0:{port}")
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
