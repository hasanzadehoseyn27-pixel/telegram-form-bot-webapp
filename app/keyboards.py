# app/keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# --- کیبورد اصلی (کیبورد پایین چت) ---
def start_keyboard(webapp_url: str, is_admin: bool) -> ReplyKeyboardMarkup:
    """
    پایین چت:
    [📝 فرم ثبت آگهی]   [⚙️ پنل مدیریتی] (فقط برای ادمین)
    """
    row1 = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    if is_admin:
        row1.append(KeyboardButton(text="⚙️ پنل مدیریتی"))
    return ReplyKeyboardMarkup(keyboard=[row1], resize_keyboard=True)

# --- ریشهٔ پنل مدیریتی (دو گزینه کنار هم + بازگشت تمام‌عرض) ---
def admin_menu_kb(is_owner: bool) -> ReplyKeyboardMarkup:
    top = [KeyboardButton(text="👤 مدیریت ادمین‌ها")]
    if is_owner:
        top.append(KeyboardButton(text="📡 مدیریت کانال‌های مجاز"))
    rows = [
        top,
        [KeyboardButton(text="🔙 بازگشت")]  # تمام‌عرض
    ]
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
