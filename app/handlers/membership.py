from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart

from ..config import SETTINGS
from ..keyboards import start_keyboard
from ..storage import (
    get_required_channel_ids,
    list_required_channels,
    is_channel_allowed,
    is_admin,
    add_required_channel,
)
from .common import to_jalali

router = Router()

# --------------------------------------------------------------------------- #
#                     بررسی دقیقِ عضویت در همهٔ کانال‌ها                      #
# --------------------------------------------------------------------------- #
async def _user_is_member(bot: Bot, user_id: int) -> bool:
    """
    True  ← اگر کاربر (یا ادمین) در *همه* کانال‌های اجباری عضو باشد
    False ← در غیر این صورت
    در صورت هرگونه خطا در واکشی وضعیت عضویت، نتیجه را False در نظر می‌گیریم.
    """
    if is_admin(user_id):
        return True

    channel_ids = get_required_channel_ids()
    if not channel_ids and SETTINGS.TARGET_GROUP_ID:
        channel_ids = [SETTINGS.TARGET_GROUP_ID]

    if not channel_ids:
        return True

    for cid in channel_ids:
        try:
            cm = await bot.get_chat_member(cid, user_id)
            status = str(getattr(cm, "status", "")).lower()
            if status not in {"member", "administrator", "creator", "owner"}:
                return False            # عضو نیست
        except Exception:
            return False                # نتوانستیم وضعیت را بگیریم → احتیاطاً False

    return True                          # در همه کانال‌ها عضو است

# --------------------------------------------------------------------------- #
#                 ساخت کیبورد «عضویت در کانال‌ها» (بدون تغییر)               #
# --------------------------------------------------------------------------- #
async def build_join_kb(bot: Bot) -> types.InlineKeyboardMarkup:
    rows: list[list[types.InlineKeyboardButton]] = []

    for ch in list_required_channels():
        cid       = int(ch.get("id", 0))
        username  = (ch.get("username") or "").lstrip("@")
        title     = ch.get("title") or username
        invite    = None

        if not title or (not username):
            try:
                info = await bot.get_chat(cid)
                fetched_title     = getattr(info, "title", "") or getattr(info, "full_name", "")
                fetched_username  = getattr(info, "username", "")

                if fetched_title and not title:
                    title = fetched_title
                if fetched_username and not username:
                    username = fetched_username

                if fetched_title or fetched_username:
                    add_required_channel(
                        cid,
                        title=fetched_title or title,
                        username=fetched_username or username,
                    )
            except Exception:
                pass

        if username:  # کانال عمومی
            rows.append(
                [types.InlineKeyboardButton(text=title or username,
                                            url=f"https://t.me/{username}")]
            )
        else:         # خصوصی
            try:
                invite = await bot.export_chat_invite_link(cid)
            except Exception:
                invite = None

            if invite:
                rows.append(
                    [types.InlineKeyboardButton(text=title or "کانال", url=invite)]
                )
            else:
                rows.append(
                    [types.InlineKeyboardButton(text=title or "کانال",
                                                callback_data=f"info:{cid}")]
                )

    rows.append(
        [types.InlineKeyboardButton(text="🔁 بررسی عضویت", callback_data="check_membership")]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=rows)

# --------------------------------------------------------------------------- #
#           بقیهٔ کد (cb_check_membership و …) بدون تغییر باقی می‌ماند        #
# --------------------------------------------------------------------------- #
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
            "❗ باید در تمام کانال‌های لیست‌شده عضو باشید، سپس دوباره روی «🔁 بررسی عضویت» بزنید.",
            reply_markup=await build_join_kb(call.bot),
        )
        return

    kb = start_keyboard(SETTINGS.WEBAPP_URL, False)
    await call.message.answer("✅ عضویت شما تایید شد. حالا می‌توانید فرم آگهی را پر کنید.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("info:"))
async def cb_info_channel(call: types.CallbackQuery):
    await call.answer(
        "این فقط نام کانال است؛ برای عضویت، کانال را با جستجوی تلگرام پیدا کنید.",
        show_alert=True
    )
