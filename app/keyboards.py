from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def start_keyboard(webapp_url: str, is_admin: bool) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    if is_admin:
        row.append(KeyboardButton(text="⚙️ پنل مدیریتی"))
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 لیست ادمین‌ها", callback_data="admin:list")],
        [InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="admin:add")],
        [InlineKeyboardButton(text="🗑 حذف ادمین", callback_data="admin:remove")],
    ])

def admin_review_kb(token: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"edit_price:{token}"),
        InlineKeyboardButton(text="📝 ویرایش توضیحات", callback_data=f"edit_desc:{token}"),
    ]
    row2 = [InlineKeyboardButton(text="✅ اعمال روی پست گروه", callback_data=f"publish:{token}")]
    row3 = [InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{token}")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])

def user_finish_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 انتشار در گروه", callback_data=f"finish:{token}")]
    ])
