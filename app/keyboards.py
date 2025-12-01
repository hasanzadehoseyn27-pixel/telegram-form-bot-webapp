# app/keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# --- کیبورد اصلی (حالت عادی) ---
def start_keyboard(_webapp_url_ignored: str, is_admin: bool) -> ReplyKeyboardMarkup:
    """
    پایین چت:
    [📝 فرم ثبت آگهی]   [⚙️ پنل مدیریتی] (فقط برای ادمین)

    نکته: این‌جا دیگر WebApp را مستقیم باز نمی‌کنیم. ابتدا با پیام «📝 فرم ثبت آگهی»
    عضویت کاربر چک می‌شود؛ سپس دکمه‌ی WebApp به‌صورت Inline داده می‌شود.
    """
    row = [KeyboardButton(text="📝 فرم ثبت آگهی")]
# --- کیبورد اصلی (حالت عادی) ---
def start_keyboard(webapp_url: str, is_admin: bool) -> ReplyKeyboardMarkup:
    """
    پایین چت:
    [📝 فرم ثبت آگهی]   [⚙️ پنل مدیریتی] (فقط برای ادمین)
    """
    row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    if is_admin:
        row.append(KeyboardButton(text="⚙️ پنل مدیریتی"))
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

# --- ریشهٔ پنل مدیریتی (Reply Keyboard) ---
def admin_root_kb(is_owner: bool) -> ReplyKeyboardMarkup:
    """
    ردیف اول: دو گزینهٔ اصلی
    ردیف دوم: بازگشت تمام‌عرض
    """
    top = [
        KeyboardButton(text="👤 مدیریت ادمین‌ها"),
    ]
    if is_owner:
        top.append(KeyboardButton(text="📡 مدیریت کانال‌های مجاز"))
    rows = [top, [KeyboardButton(text="🔙 بازگشت")]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

# --- زیرمنو: مدیریت ادمین‌ها ---
def admin_admins_kb() -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton(text="📋 لیست ادمین‌ها"),
        KeyboardButton(text="➕ افزودن ادمین"),
        KeyboardButton(text="🗑 حذف ادمین"),
    ]
    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)

# --- زیرمنو: مدیریت کانال‌های مجاز (فقط OWNER) ---
def admin_allowed_kb() -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton(text="➕ افزودن کانال مجاز"),
        KeyboardButton(text="🗑 حذف کانال مجاز"),
        KeyboardButton(text="📋 لیست کانال‌های مجاز"),
    ]
    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)

# --- دکمهٔ Inline برای بازکردن WebApp فرم ---
def open_form_kb(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 بازکردن فرم آگهی", web_app=WebAppInfo(url=webapp_url))]
    ])

# --- دکمهٔ Inline برای عضویت کانال ---
def join_channel_kb(channel_username: str) -> InlineKeyboardMarkup:
    # channel_username مثل: "@tetsbankkhodro"
    url = f"https://t.me/{channel_username.lstrip('@')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"بانک خودرو — {channel_username}", url=url)]
    ])

# --- دکمه انتشار برای کاربر (INLINE) ---
def user_finish_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 انتشار در گروه", callback_data=f"finish:{token}")]
    ])

# --- کیبورد بررسی برای ادمین‌ها (INLINE) ---
def admin_review_kb(token: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"edit_price:{token}"),
        InlineKeyboardButton(text="📝 ویرایش توضیحات", callback_data=f"edit_desc:{token}"),
    ]
    row2 = [InlineKeyboardButton(text="✅ اعمال روی پست گروه", callback_data=f"publish:{token}")]
    row3 = [InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{token}")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])
