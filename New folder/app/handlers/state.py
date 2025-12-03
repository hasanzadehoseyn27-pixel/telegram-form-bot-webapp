"""
وضعیت‌های سراسریِ حینِ اجرا (در یک فایل مجزا)
"""
MAX_PHOTOS = 5

PENDING: dict[str, dict] = {}
PHOTO_WAIT: dict[int, dict] = {}
ADMIN_EDIT_WAIT: dict[int, dict] = {}
ADMIN_WAIT_INPUT: dict[int, dict] = {}
ACCESS_CH_WAIT: dict[int, dict] = {}
MEMBERS_CH_WAIT: dict[int, dict] = {}
