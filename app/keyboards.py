from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

ADMIN_BTN_TEXT = "⚙️ پنل مدیریتی"

def start_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def start_keyboard_owner(webapp_url: str) -> ReplyKeyboardMarkup:
    row = [
        KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url)),
        KeyboardButton(text=ADMIN_BTN_TEXT),
    ]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def admin_review_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"edit_price:{token}"),
            InlineKeyboardButton(text="📝 ویرایش توضیحات", callback_data=f"edit_desc:{token}"),
        ],
        [
            InlineKeyboardButton(text="✅ اعمال روی پست گروه", callback_data=f"publish:{token}"),
            InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{token}"),
        ],
    ])
