from aiogram import Router, types, F
from aiogram.filters import CommandStart
from .state import *
from ..config import SETTINGS
from ..keyboards import start_keyboard
from ..storage import (
    get_required_channel_ids,
    list_required_channels,
    is_channel_allowed,
    is_admin,
)
from .common import to_jalali

router = Router()


async def _user_is_member(bot, user_id: int) -> bool:
    if is_admin(user_id):
        return True

    channel_ids = get_required_channel_ids()
    if not channel_ids and SETTINGS.TARGET_GROUP_ID:
        channel_ids = [SETTINGS.TARGET_GROUP_ID]

    if not channel_ids:
        return True

    ok_any = False
    for cid in channel_ids:
        try:
            cm = await bot.get_chat_member(cid, user_id)
            status = str(getattr(cm, "status", "")).lower()
            ok_any = True
            if status not in {"member", "administrator", "creator", "owner"}:
                return False
        except Exception:
            continue

    return True if ok_any else True  # fail‑open


def _join_kb() -> types.InlineKeyboardMarkup:
    """
    دکمه‌های عضویت در کانال‌ها:
    ● اگر username دارد → لینک
    ● اگر خصوصی است → فقط نام (Callback بی‌اثر)
      * دیگر ID نمایش داده نمی‌شود.
    """
    buttons: list[list[types.InlineKeyboardButton]] = []
    for ch in list_required_channels():
        cid = int(ch.get("id", 0))
        username = (ch.get("username") or "").lstrip("@")
        title = ch.get("title") or username or "کانال"

        if username:  # کانال عمومی
            buttons.append(
                [types.InlineKeyboardButton(text=title, url=f"https://t.me/{username}")]
            )
        else:  # خصوصی → فقط نشان می‌دهیم
            buttons.append(
                [types.InlineKeyboardButton(text=title, callback_data=f"info:{cid}")]
            )

    if not buttons:  # حالت قدیمی
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text="کانال اصلی", url="https://t.me/tetsbankkhodro"
                )
            ]
        )

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔁 بررسی عضویت", callback_data="check_membership"
            )
        ]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "check_membership")
async def cb_check_membership(call: types.CallbackQuery):
    uid = call.from_user.id
    if is_admin(uid):
        kb = start_keyboard(SETTINGS.WEBAPP_URL, True)
        await call.message.answer("شما ادمین هستید و نیازی به چک عضویت ندارید.", reply_markup=kb)
        await call.answer()
        return

    ok = await _user_is_member(call.bot, uid)
    if not ok:
        await call.answer("هنوز در همهٔ کانال‌ها عضو نیستید.", show_alert=True)
        await call.message.answer(
            "❗ باید در تمام کانال‌های لیست‌شده عضو باشید، سپس دوباره روی «🔁 بررسی عضویت» بزنید."
        )
        return

    kb = start_keyboard(SETTINGS.WEBAPP_URL, False)
    await call.message.answer("✅ عضویت شما تایید شد. حالا می‌توانید فرم آگهی را پر کنید.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("info:"))
async def cb_info_channel(call: types.CallbackQuery):
    await call.answer(
        "این فقط نام کانال است؛ برای عضویت، کانال را با جستجوی تلگرام پیدا کنید.", show_alert=True
    )
