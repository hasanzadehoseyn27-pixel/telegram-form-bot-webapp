from __future__ import annotations
import json
from pathlib import Path
from datetime import date

DATA = Path("/tmp/bot_data")
DATA.mkdir(parents=True, exist_ok=True)
DAILY_FILE = DATA / "daily.json"


def next_daily_number() -> tuple[int, str]:
    """شمارندهٔ سراسری آگهی (ریست روزانه)."""
    today = date.today().isoformat()
    data = {"date": today, "num": 0}

    if DAILY_FILE.exists():
        try:
            data = json.loads(DAILY_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    data["date"] = today
    data["num"] = int(data.get("num", 0)) + 1

    try:
        DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return data["num"], today
