from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

def start_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def admin_review_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"edit_price:{token}")],
        [InlineKeyboardButton(text="✏️ ویرایش توضیحات", callback_data=f"edit_desc:{token}")],
        [InlineKeyboardButton(text="✅ انتشار", callback_data=f"publish:{token}")],
        [InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{token}")],
    ])
