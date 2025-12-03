from aiogram import Router, types
from aiogram.filters import CommandStart

from ..config import SETTINGS
from ..keyboards import start_keyboard
from .membership import _user_is_member, build_join_kb      # ← اصلاح import
from ..storage import is_admin
from .state import *

router = Router()


@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است.")
        return

    if is_admin(message.from_user.id):
        kb = start_keyboard(SETTINGS.WEBAPP_URL, True)
        await message.answer("برای ثبت آگهی، دکمه زیر را بزنید:", reply_markup=kb)
        return

    # ----------- بررسی عضویت در کانال‌های اجباری ------------- #
    if not await _user_is_member(message.bot, message.from_user.id):
        await message.answer(
            "⛔ برای استفاده از ربات، ابتدا در همهٔ کانال‌های زیر عضو شوید و سپس روی «🔁 بررسی عضویت» بزنید:",
            reply_markup=await build_join_kb(message.bot),   # ← جایگزین _join_kb()
        )
        return

    kb = start_keyboard(SETTINGS.WEBAPP_URL, False)
    await message.answer("برای ثبت آگهی، دکمه زیر را بزنید:", reply_markup=kb)
