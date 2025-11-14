import asyncio
from app.config import build_bot_and_dispatcher
from app.handlers import router

async def main():
    bot, dp = build_bot_and_dispatcher()
    dp.include_router(router)
    print("Bot is running…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
