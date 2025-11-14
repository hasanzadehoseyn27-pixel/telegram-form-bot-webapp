import json, os
from zoneinfo import ZoneInfo
from datetime import datetime

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data_state.json")

def _load():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(s: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def next_daily_number(tz: str = "Asia/Tehran"):
    s = _load()
    today = datetime.now(ZoneInfo(tz)).date().isoformat()
    if s.get("counter_date") != today:
        s["counter_date"] = today
        s["counter"] = 0
    s["counter"] += 1
    _save(s)
    return s["counter"], today
