
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

def start_keyboard(webapp_url: str, *, is_owner: bool, admin_url: str | None = None) -> ReplyKeyboardMarkup:
    """اگر مالک است: دو دکمه (پنل مدیریتی + فرم). در غیر این صورت: فقط فرم."""
    if is_owner and admin_url:
        row = [
            KeyboardButton(text="⚙️ پنل مدیریتی", web_app=WebAppInfo(url=admin_url)),
            KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url)),
        ]
    else:
        row = [KeyboardButton(text="📝 فرم ثبت آگهی", web_app=WebAppInfo(url=webapp_url))]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)
