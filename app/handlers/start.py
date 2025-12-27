from aiogram import Router, types
from aiogram.filters import CommandStart

from ..config import SETTINGS
from ..keyboards import start_keyboard
from .membership import _user_is_member, build_join_kb
from ..storage import is_admin
from .state import *

router = Router()


@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است.")
        return

    # حالت ۱: اگر کاربر ادمین باشد
    if is_admin(message.from_user.id):
        kb = start_keyboard(SETTINGS.WEBAPP_URL, True)
        await message.answer(
            "به ربات بانک خودرو خوش آمدید 🌹\n\nبرای ثبت آگهی یا ورود به پنل، از دکمه‌های زیر استفاده کنید:",
            reply_markup=kb
        )
        return

    # ----------- بررسی عضویت در کانال‌های اجباری ------------- #
    if not await _user_is_member(message.bot, message.from_user.id):
        await message.answer(
            "⛔ برای استفاده از ربات، ابتدا در همهٔ کانال‌های زیر عضو شوید و سپس روی «🔁 بررسی عضویت» بزنید:",
            reply_markup=await build_join_kb(message.bot),
        )
        return

    # حالت ۲: اگر کاربر عادی باشد و عضویتش تایید شده باشد
    kb = start_keyboard(SETTINGS.WEBAPP_URL, False)
    await message.answer(
        "به ربات بانک خودرو خوش آمدید 🌹\n\nبرای ثبت آگهی، دکمه زیر را بزنید:", 
        reply_markup=kb
    )