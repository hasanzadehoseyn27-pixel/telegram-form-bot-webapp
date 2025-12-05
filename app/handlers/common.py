import re
import jdatetime

from aiogram import html

__all__ = [
    "to_jalali",
    "contains_persian_digits",
    "price_words",
    "_price_million_to_toman_str",
    "_parse_admin_price",
]

# ---------------------------- helpers ---------------------------------------

def to_jalali(date_iso: str) -> str:
    y, m, d = map(int, date_iso.split("-"))
    j = jdatetime.date.fromgregorian(year=y, month=m, day=d)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"


def contains_persian_digits(s: str) -> bool:
    return bool(re.search(r"[\u06F0-\u06F9\u0660-\u0669]", s or ""))


def normalize_digits(s: str) -> str:
    """تبدیل ارقام فارسی و عربی به لاتین"""
    if not s:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    trans = {ord(p): str(i) for i, p in enumerate(persian)}
    trans.update({ord(a): str(i) for i, a in enumerate(arabic)})
    return s.translate(trans)


def clean_text(s: str) -> str:
    """حذف تمام کاراکترهای مخفی تلگرام که regex را خراب می‌کند"""
    if not s:
        return ""
    hidden = [
        "\u200f",  # RTL mark
        "\u200e",  # LTR mark
        "\u202a",  # LRE
        "\u202b",  # RLE
        "\u202c",  # PDF
        "\u202d",  # LRO
        "\u202e",  # RLO
    ]
    for h in hidden:
        s = s.replace(h, "")
    return s


def price_words(num: int) -> str:
    if num >= 100_000_000_000:
        num = 100_000_000_000
    parts = []
    if num >= 1_000_000_000:
        b = num // 1_000_000_000
        parts.append(f"{b} میلیارد")
        num %= 1_000_000_000
    if num >= 1_000_000:
        m = num // 1_000_000
        parts.append(f"{m} میلیون")
        num %= 1_000_000
    if num >= 1_000:
        k = num // 1_000
        parts.append(f"{k} هزار")
        num %= 1_000
    if num > 0:
        parts.append(f"{num}")
    return " و ".join(parts) + " تومان"


# تبدیل ورودی million به تومان
def _price_million_to_toman_str(raw: str) -> tuple[bool, int]:
    s = clean_text(normalize_digits(raw or "")).replace(" ", "")
    s = s.replace(",", ".").replace("\u066B", ".")
    if not s:
        return True, 0
    if not re.fullmatch(r"\d+(\.\d{1,3})?", s):
        return False, 0
    v = float(s)
    return True, int(round(v * 1_000_000))


def _parse_admin_price(text: str) -> tuple[bool, int]:
    """
    ویرایش قیمت توسط ادمین — دقیقاً مثل منطق validate فرم کاربر
    هر عددی مثل:
        80
        120.5
        2500
        12500
    با اعشار 1 تا 3 رقم مجاز است.
    """

    # نرمال‌سازی و حذف کاراکترهای مخفی
    s = normalize_digits(clean_text(text or "")).strip()
    s = s.replace(",", ".").replace("\u066B", ".")

    # فقط اجازه اعداد صحیح یا اعشاری
    if not re.fullmatch(r"\d+(\.\d{1,3})?", s):
        return False, 0

    try:
        million = float(s)
    except:
        return False, 0

    toman = int(round(million * 1_000_000))
    return True, toman
