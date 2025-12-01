from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)


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


# --- کیبورد پنل مدیریتی (Reply Keyboard) ---
def admin_menu_kb(is_owner: bool) -> ReplyKeyboardMarkup:
    """
    جایگزین کیبورد اصلی وقتی ادمین روی «⚙️ پنل مدیریتی» می‌زند.
    اگر OWNER باشد، دکمه «⚡ مدیریت دسترسی» هم اضافه می‌شود.
    """
    row1 = [
        KeyboardButton(text="BBBs لیست ادمین‌ها"),
        KeyboardButton(text="➕ افزودن ادمین"),
    ]
    row2 = [
        KeyboardButton(text="🗑 حذف ادمین"),
        KeyboardButton(text="🔙 بازگشت"),
    ]
    rows = [row1, row2]

    if is_owner:
        # ردیف جدا برای مدیریت دسترسی
        rows.append([KeyboardButton(text="⚡ مدیریت دسترسی")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# --- دکمه انتشار برای کاربر (INLINE) ---
def user_finish_kb(token: str) -> InlineKeyboardMarkup:
    # کاربر بعد از ارسال عکس‌ها با این دکمه پست را منتشر می‌کند
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
