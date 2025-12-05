from __future__ import annotations
import json
from pathlib import Path
from datetime import date

DATA = Path("/tmp/bot_data")
DATA.mkdir(parents=True, exist_ok=True)
DAILY_FILE = DATA / "daily.json"


def next_daily_number() -> tuple[int, str]:
    """
    شمارندهٔ سراسری آگهی (بدون ریست روزانه).

    - در فایل DAILY_FILE مقدار آخر ذخیره می‌شود.
    - هر بار صدا زده شود، num یک واحد افزایش می‌یابد.
    - تاریخ امروز نیز برگردانده می‌شود تا در کپشن استفاده شود.
    """
    today = date.today().isoformat()

    # مقدار پیش‌فرض
    num = 0

    # اگر فایل قبلاً ساخته شده است، عدد قبلی را می‌خوانیم
    if DAILY_FILE.exists():
        try:
            saved = json.loads(DAILY_FILE.read_text(encoding="utf-8")) or {}
            if isinstance(saved, dict):
                num = int(saved.get("num", 0))
        except Exception:
            # اگر هر مشکلی بود، از num=0 شروع می‌کنیم
            pass

    # همیشه یک عدد زیاد می‌کنیم
    num += 1

    data = {"date": today, "num": num}

    # ذخیره روی دیسک
    try:
        DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    # برگرداندن شماره و تاریخ امروز
    return num, today
