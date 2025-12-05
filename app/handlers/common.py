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


# تبدیل million-تومانیِ ورودیِ کاربر به رقم تومان
def _price_million_to_toman_str(raw: str) -> tuple[bool, int]:
    s = normalize_digits(raw or "").replace(" ", "").replace(",", ".").replace("\u066B", ".")
    if not s:
        return True, 0

    if not re.fullmatch(r"\d+(\.\d{1,3})?", s):
        return False, 0

    v = float(s)
    return True, int(round(v * 1_000_000))


def _parse_admin_price(text: str) -> tuple[bool, int]:
    """منطق قیمت ادمین مثل فرم اولیه → هر عددی با اعشار 1 تا 3 رقم مجاز است"""
    s = normalize_digits(text or "").strip().replace(",", ".").replace("\u066B", ".")

    # اگر چیز غیرعددی بود
    if not re.fullmatch(r"\d+(\.\d{1,3})?", s):
        return False, 0

    try:
        million = float(s)
    except:
        return False, 0

    toman = int(round(million * 1_000_000))
    return True, toman
