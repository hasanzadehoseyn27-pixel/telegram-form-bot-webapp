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
    هر بار که صدا زده شود، عدد را ۱ واحد زیاد می‌کند و
    تاریخ امروز را نیز برمی‌گرداند.
    """
    today = date.today().isoformat()

    # مقدار پیش‌فرض
    data: dict = {"date": today, "num": 0}

    # اگر قبلاً فایلی وجود دارد، num قبلی را می‌خوانیم
    if DAILY_FILE.exists():
        try:
            loaded = json.loads(DAILY_FILE.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                # num قبلی را نگه می‌داریم (اگر باشد)
                if "num" in loaded:
                    data["num"] = int(loaded.get("num", 0))
        except Exception:
            pass

    # همیشه ۱ واحد زیاد می‌کنیم (بدون توجه به تاریخ ذخیره‌شده)
    data["num"] = int(data.get("num", 0)) + 1
    data["date"] = today

    try:
        DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return data["num"], today
