from __future__ import annotations
import json, os
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DAILY_FILE = DATA / "daily.json"
ADMINS_FILE = DATA / "admins.json"

# --------- شماره‌ی روزانه آگهی ---------
def next_daily_number() -> tuple[int, str]:
    today = date.today().isoformat()
    data = {"date": today, "num": 0}
    if DAILY_FILE.exists():
        try:
            data = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    if data.get("date") != today:
        data = {"date": today, "num": 0}
    data["num"] = int(data.get("num", 0)) + 1
    DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data["num"], today

# --------- مدیریت ادمین‌ها (پایدار) ---------
_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0

def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
    """فقط یک بار از config صدا زده می‌شود تا ادمین‌ها مقداردهی شوند."""
    global _ADMIN_SET, _OWNER_ID
    _OWNER_ID = int(owner_id or 0)

    saved: set[int] = set()
    if ADMINS_FILE.exists():
        try:
            saved = set(json.loads(ADMINS_FILE.read_text(encoding="utf-8")) or [])
        except Exception:
            saved = set()

    _ADMIN_SET = set(initial_env_admins or set()) | saved
    if _OWNER_ID:
        _ADMIN_SET.add(_OWNER_ID)
    _persist()

def _persist() -> None:
    ADMINS_FILE.write_text(json.dumps(sorted(_ADMIN_SET), ensure_ascii=False), encoding="utf-8")

def list_admins() -> list[int]:
    return sorted(_ADMIN_SET)

def add_admin(uid: int) -> bool:
    uid = int(uid)
    if uid in _ADMIN_SET:
        return False
    _ADMIN_SET.add(uid)
    _persist()
    return True

def remove_admin(uid: int) -> bool:
    uid = int(uid)
    if uid == _OWNER_ID:
        return False
    if uid in _ADMIN_SET:
        _ADMIN_SET.remove(uid)
        _persist()
        return True
    return False

def is_admin(uid: int) -> bool:
    return int(uid) in _ADMIN_SET

