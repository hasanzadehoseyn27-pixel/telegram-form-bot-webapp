from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def start_keyboard(webapp_url: str, is_admin: bool) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    if is_admin:
        row.append(KeyboardButton(text="⚙️ پنل مدیریتی"))
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def publish_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📣 انتشار در گروه")]],
        resize_keyboard=True
    )

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 لیست ادمین‌ها", callback_data="admin:list")],
        [InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="admin:add")],
        [InlineKeyboardButton(text="🗑 حذف ادمین", callback_data="admin:remove")],
        [InlineKeyboardButton(text="📍 مدیریت مقصدها", callback_data="dest:menu")],
    ])

def admin_review_kb(token: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"edit_price:{token}"),
        InlineKeyboardButton(text="📝 ویرایش توضیحات", callback_data=f"edit_desc:{token}"),
    ]
    row2 = [InlineKeyboardButton(text="✅ اعمال روی پست گروه", callback_data=f"publish:{token}")]
    row3 = [InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{token}")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])

def dest_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن مقصد", callback_data="dest:add")],
        [InlineKeyboardButton(text="📜 لیست مقصدها", callback_data="dest:list")],
    ])

def dest_list_kb(items: list[tuple[int, str]], active: int|None) -> InlineKeyboardMarkup:
    rows = []
    for cid, name in items:
        mark = "✅ " if active and cid == active else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{name} ({cid})", callback_data=f"dest:activate:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[
        InlineKeyboardButton(text="مقصدی ثبت نشده است", callback_data="noop")
    ]])
