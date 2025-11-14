import asyncio
from app.config import build_bot_and_dispatcher, SETTINGS
from app.handlers import router
from app.storage import bootstrap_admins

async def main():
    bot, dp = build_bot_and_dispatcher()
    bootstrap_admins(SETTINGS.ADMIN_IDS, SETTINGS.OWNER_ID)  # مهم
    dp.include_router(router)
    print("Bot is running…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
