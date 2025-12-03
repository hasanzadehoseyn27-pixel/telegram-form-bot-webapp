# --------------------------------------------------------------------------- #
#             ساخت کیبورد «عضویت در کانال‌ها» به‌صورت پویا و لینک‌دار          #
# --------------------------------------------------------------------------- #
from aiogram import types, Bot
from ..storage import add_required_channel          # برای به‌روزرسانی عنوان/یوزرنیم

async def build_join_kb(bot: Bot) -> types.InlineKeyboardMarkup:
    """
    کیبورد کانال‌های اجباری را برمی‌گرداند.

    ● کانال عمومی  → دکمهٔ لینک‌دار t.me/<username>
    ● کانال خصوصی و ربات=ادمین → لینک دعوت دائم
    ● سایر موارد      → فقط نام (Callback بی‌اثر)
    در صورت نبود عنوان/یوزرنیم، یک بار از Telegram واکشی و در فایل ذخیره می‌شود.
    """
    rows: list[list[types.InlineKeyboardButton]] = []

    for ch in list_required_channels():
        cid       = int(ch.get("id", 0))
        username  = (ch.get("username") or "").lstrip("@")
        title     = ch.get("title") or username                 # ممکن است خالی باشد
        invite    = None

        # ---- اگر عنوان یا یوزرنیم نداریم، یک بار از API می‌گیریم ---- #
        if not title or (not username):
            try:
                info = await bot.get_chat(cid)
                fetched_title     = getattr(info, "title", "") or getattr(info, "full_name", "")
                fetched_username  = getattr(info, "username", "")      # برای کانال عمومی

                if fetched_title and not title:
                    title = fetched_title
                if fetched_username and not username:
                    username = fetched_username

                # ذخیره در فایل (فقط یک بار کافی است)
                if fetched_title or fetched_username:
                    add_required_channel(
                        cid,
                        title=fetched_title or title,
                        username=fetched_username or username,
                    )
            except Exception:
                pass                                                 # دسترسی یا خطای شبکه

        # ---- تصمیم نهایی برای نوع دکمه ---- #
        if username:                                                # کانال عمومی
            rows.append(
                [types.InlineKeyboardButton(text=title or username,
                                            url=f"https://t.me/{username}")]
            )
        else:                                                       # خصوصی
            # تلاش برای ساخت لینک دعوت (در صورتی که ربات ادمین باشد)
            try:
                invite = await bot.export_chat_invite_link(cid)
            except Exception:
                invite = None

            if invite:
                rows.append([types.InlineKeyboardButton(text=title or "کانال", url=invite)])
            else:
                rows.append([types.InlineKeyboardButton(text=title or "کانال",
                                                        callback_data=f"info:{cid}")])

    # دکمهٔ «بررسی عضویت» در انتها
    rows.append(
        [types.InlineKeyboardButton(text="🔁 بررسی عضویت", callback_data="check_membership")]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=rows)
