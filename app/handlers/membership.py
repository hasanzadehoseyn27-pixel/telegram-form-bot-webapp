from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart

from ..config import SETTINGS
from ..keyboards import start_keyboard
from ..storage import (
    get_required_channel_ids,
    list_required_channels,
    is_channel_allowed,
    is_admin,
    add_required_channel,           # ← برای به‌روزرسانی عنوان/یوزرنیم
)
from .common import to_jalali

router = Router()

# --------------------------------------------------------------------------- #
#                       بررسی عضویت کاربر در کانال‌ها                         #
# --------------------------------------------------------------------------- #
async def _user_is_member(bot: Bot, user_id: int) -> bool:
    """
    اگر کاربر (یا ادمین‌ها) در تمام کانال‌های «اجباری» عضو باشد → True
    در غیر این صورت → False
    """
    if is_admin(user_id):
        return True

    channel_ids = get_required_channel_ids()
    if not channel_ids and SETTINGS.TARGET_GROUP_ID:
        channel_ids = [SETTINGS.TARGET_GROUP_ID]

    if not channel_ids:
        return True      # هیچ کانالی تعریف نشده است

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

    return True if ok_any else True   # حالت fail‑open (اگر خطای API داشتیم)

# --------------------------------------------------------------------------- #
#             ساخت کیبورد «عضویت در کانال‌ها» به‌صورت پویا و لینک‌دار          #
# --------------------------------------------------------------------------- #
async def build_join_kb(bot: Bot) -> types.InlineKeyboardMarkup:
    """
    ● کانال عمومی  → دکمهٔ لینک‌دار t.me/<username>
    ● کانال خصوصی و ربات=ادمین → لینک دعوت دائم
    ● سایر موارد      → فقط نام (Callback بی‌اثر)
    """
    rows: list[list[types.InlineKeyboardButton]] = []

    for ch in list_required_channels():
        cid       = int(ch.get("id", 0))
        username  = (ch.get("username") or "").lstrip("@")
        title     = ch.get("title") or username
        invite    = None

        # --- اگر اطلاعات ناقص است، یک بار از تلگرام واکشی می‌کنیم --- #
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

        # --- دکمه --- #
        if username:  # عمومی
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

    # دکمهٔ بررسی عضویت
    rows.append(
        [types.InlineKeyboardButton(text="🔁 بررسی عضویت", callback_data="check_membership")]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=rows)

# --------------------------------------------------------------------------- #
#                 سایر callback‑ها و فرمان‌های بخش عضویت                     #
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
