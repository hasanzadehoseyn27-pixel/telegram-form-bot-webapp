"""
وضعیت‌های سراسریِ حینِ اجرا (در یک فایل مجزا)
"""

# تعداد مجاز عکس‌های هر آگهی
MAX_PHOTOS = 5

# نگهداری آگهی‌های در انتظار بررسی
PENDING: dict[str, dict] = {}

# وضعیت کاربر هنگام ارسال عکس‌ها
PHOTO_WAIT: dict[int, dict] = {}

# وضعیت ویرایش قیمت/توضیح توسط ادمین
ADMIN_EDIT_WAIT: dict[int, dict] = {}

# وضعیت افزودن/حذف ادمین (منتظر ورودی)
ADMIN_WAIT_INPUT: dict[int, dict] = {}

# وضعیت افزودن/حذف کانال‌های اجباری (کانال‌های من)
MEMBERS_CH_WAIT: dict[int, dict] = {}
