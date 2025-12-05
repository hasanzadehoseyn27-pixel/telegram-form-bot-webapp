from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# --------------------------------------------------------------------------- #
#                            کیبورد اصلی                                      #
# --------------------------------------------------------------------------- #

def start_keyboard(webapp_url: str, is_admin: bool) -> ReplyKeyboardMarkup:
    """
    کیبورد اصلی ربات – شامل دکمه فرم و دکمه پنل مدیریتی (برای ادمین‌ها)
    """
    row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    if is_admin:
        row.append(KeyboardButton(text="⚙️ پنل مدیریتی"))
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#                      ریشه پنل مدیریتی                                       #
# --------------------------------------------------------------------------- #

def admin_root_kb(is_owner: bool) -> ReplyKeyboardMarkup:
    """
    منوی اصلی پنل مدیر – شامل:
    - مدیریت ادمین‌ها
    - مدیریت کانال‌های من (فقط Owner)
    """
    top = [KeyboardButton(text="👤 مدیریت ادمین‌ها")]

    if is_owner:
        top.append(KeyboardButton(text="📣 کانال‌های من"))

    rows = [
        top,
        [KeyboardButton(text="🔙 بازگشت")]
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# --------------------------------------------------------------------------- #
#                      زیرمنو: مدیریت ادمین‌ها                                 #
# --------------------------------------------------------------------------- #

def admin_admins_kb() -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton(text="📋 لیست ادمین‌ها"),
        KeyboardButton(text="➕ افزودن ادمین"),
        KeyboardButton(text="🗑 حذف ادمین"),
    ]
    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#          زیرمنو: مدیریت کانال‌های مجاز ارسال (برای OWNER)                  #
# --------------------------------------------------------------------------- #

def admin_allowed_kb() -> ReplyKeyboardMarkup:
    """
    منوی مدیریت «کانال‌های مجاز ارسال» که در admin_panel.py
    برای گزینه «📡 مدیریت کانال‌های مجاز» استفاده می‌شود.
    """
    row1 = [
        KeyboardButton(text="➕ افزودن کانال مجاز"),
        KeyboardButton(text="🗑 حذف کانال مجاز"),
        KeyboardButton(text="📋 لیست کانال‌های مجاز"),
    ]
    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#          زیرمنو: کانال‌های من (عضویت اجباری)                                #
# --------------------------------------------------------------------------- #

def admin_my_channels_kb() -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton(text="➕ افزودن کانال من"),
        KeyboardButton(text="🗑 حذف کانال من"),
        KeyboardButton(text="📋 لیست کانال‌های من"),
    ]
    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#                دکمه انتشار نهایی برای کاربر (پس از ارسال عکس‌ها)            #
# --------------------------------------------------------------------------- #

def user_finish_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 انتشار در گروه", callback_data=f"finish:{token}")]
    ])


# --------------------------------------------------------------------------- #
#                     کیبورد بررسی و ویرایش برای ادمین‌ها                     #
# --------------------------------------------------------------------------- #

def admin_review_kb(token: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"edit_price:{token}"),
        InlineKeyboardButton(text="📝 ویرایش توضیحات", callback_data=f"edit_desc:{token}"),
    ]
    row2 = [
        InlineKeyboardButton(text="✅ اعمال روی پست گروه", callback_data=f"publish:{token}")
    ]
    row3 = [
        InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{token}")
    ]

    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])
