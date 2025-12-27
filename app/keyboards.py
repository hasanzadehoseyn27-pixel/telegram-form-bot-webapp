from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# --------------------------------------------------------------------------- #
#                             کیبورد اصلی                                     #
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
#                        ریشه پنل مدیریتی                                     #
# --------------------------------------------------------------------------- #

def admin_root_kb(is_owner: bool) -> ReplyKeyboardMarkup:
    """
    منوی اصلی پنل مدیر.
    - مدیریت ادمین‌ها: برای همه (چون ادمین معمولی باید لیست را ببیند)
    - سایر موارد: فقط Owner
    """
    # ردیف اول: دکمه‌هایی که Owner می‌بیند
    top_owner = []
    if is_owner:
        top_owner.append(KeyboardButton(text="📣 کانال‌های من"))
        top_owner.append(KeyboardButton(text="🎯 مدیریت مقصدها"))

    # ردیف دوم: مدیریت ادمین‌ها (برای همه) و بازگشت
    # نکته: ادمین معمولی فقط می‌تواند لیست را ببیند (در کیبورد بعدی محدود می‌شود)
    rows = [
        [KeyboardButton(text="👤 مدیریت ادمین‌ها")],
    ]
    
    if top_owner:
        rows.insert(0, top_owner)
        
    rows.append([KeyboardButton(text="🔙 بازگشت")])
    
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# --------------------------------------------------------------------------- #
#                       زیرمنو: مدیریت ادمین‌ها                                #
# --------------------------------------------------------------------------- #

def admin_admins_kb(is_owner: bool) -> ReplyKeyboardMarkup:
    """
    اگر Owner باشد: همه دکمه‌ها (لیست، افزودن، حذف)
    اگر ادمین معمولی باشد: فقط دکمه «لیست ادمین‌ها»
    """
    if is_owner:
        row1 = [
            KeyboardButton(text="📋 لیست ادمین‌ها"),
            KeyboardButton(text="➕ افزودن ادمین"),
            KeyboardButton(text="🗑 حذف ادمین"),
        ]
    else:
        # ادمین معمولی فقط لیست را می‌بیند
        row1 = [KeyboardButton(text="📋 لیست ادمین‌ها")]

    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#           زیرمنو: مدیریت کانال‌های مجاز ارسال (برای OWNER)                  #
# --------------------------------------------------------------------------- #

def admin_allowed_kb() -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton(text="➕ افزودن کانال مجاز"),
        KeyboardButton(text="🗑 حذف کانال مجاز"),
        KeyboardButton(text="📋 لیست کانال‌های مجاز"),
    ]
    row2 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#           زیرمنو: کانال‌های من (عضویت اجباری)                                #
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
#           زیرمنو: مدیریت مقصدها (برای OWNER)                                #
# --------------------------------------------------------------------------- #

def admin_destinations_kb() -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton(text="📋 لیست مقصدها"),
        KeyboardButton(text="➕ افزودن مقصد"),
    ]
    row2 = [
        KeyboardButton(text="✅ انتخاب مقصد فعال"),
        KeyboardButton(text="🗑 حذف مقصد"),
    ]
    row3 = [KeyboardButton(text="🔙 بازگشت به پنل")]
    return ReplyKeyboardMarkup(keyboard=[row1, row2, row3], resize_keyboard=True)


# --------------------------------------------------------------------------- #
#                دکمه انتشار نهایی برای کاربر (پس از ارسال عکس‌ها)             #
# --------------------------------------------------------------------------- #

def user_finish_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید نهایی", callback_data=f"finish:{token}")]
    ])


# --------------------------------------------------------------------------- #
#                     کیبورد بررسی و ویرایش برای ادمین‌ها                      #
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