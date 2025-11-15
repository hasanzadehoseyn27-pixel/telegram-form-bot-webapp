from __future__ import annotations
import json
from pathlib import Path
from datetime import date

# ریشه پروژه و مسیر فایل‌های داده
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DAILY_FILE = DATA / "daily.json"
ADMINS_FILE = DATA / "admins.json"
DESTS_FILE = DATA / "destinations.json"

# ---------------- شماره آگهی روزانه ----------------
def next_daily_number() -> tuple[int, str]:
    """(شماره امروز, تاریخ ISO) را برمی‌گرداند و ذخیره می‌کند."""
    today = date.today().isoformat()
    data = {"date": today, "num": 0}
    if DAILY_FILE.exists():
        try:
            data = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {"date": today, "num": 0}
    if data.get("date") != today:
        data = {"date": today, "num": 0}
    data["num"] = int(data.get("num", 0)) + 1
    DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data["num"], today

# ---------------- مدیریت ادمین‌ها (پایدار) ----------------
_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0

def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
    """فقط یک‌بار در استارتاپ صدا بزنید."""
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
    _persist_admins()

def _persist_admins() -> None:
    ADMINS_FILE.write_text(
        json.dumps(sorted(_ADMIN_SET), ensure_ascii=False),
        encoding="utf-8",
    )

def list_admins() -> list[int]:
    return sorted(_ADMIN_SET)

def add_admin(uid: int) -> bool:
    uid = int(uid)
    if uid in _ADMIN_SET:
        return False
    _ADMIN_SET.add(uid)
    _persist_admins()
    return True

def remove_admin(uid: int) -> bool:
    uid = int(uid)
    if uid == _OWNER_ID:
        return False  # صاحب حذف نمی‌شود
    if uid in _ADMIN_SET:
        _ADMIN_SET.remove(uid)
        _persist_admins()
        return True
    return False

def is_admin(uid: int) -> bool:
    return int(uid) in _ADMIN_SET

# ---------------- مدیریت مقصدها (گروه/کانال) ----------------
# ساختار فایل DESTS_FILE :
# {"list":[{"id":-100123,"title":"گروه A"},{"id":-100456,"title":"کانال X"}],"active":-100123}
_DESTS: dict = {"list": [], "active": 0}

def _load_dests() -> None:
    global _DESTS
    if DESTS_FILE.exists():
        try:
            _DESTS = json.loads(DESTS_FILE.read_text(encoding="utf-8")) or {"list": [], "active": 0}
        except Exception:
            _DESTS = {"list": [], "active": 0}
    else:
        _DESTS = {"list": [], "active": 0}

def _save_dests() -> None:
    DESTS_FILE.write_text(json.dumps(_DESTS, ensure_ascii=False), encoding="utf-8")

def bootstrap_destinations(default_id: int, default_title: str = "") -> None:
    """در استارتاپ صدا بزن؛ اگر فایل خالی بود، مقدار .env را به‌عنوان مقصد اولیه ثبت می‌کند."""
    _load_dests()
    if not _DESTS["list"] and default_id:
        _DESTS["list"].append({"id": int(default_id), "title": str(default_title or "")})
    if not _DESTS.get("active") and default_id:
        _DESTS["active"] = int(default_id)
    _save_dests()

def list_destinations() -> list[dict]:
    _load_dests()
    return list(_DESTS.get("list", []))

def add_destination(chat_id: int, title: str = "") -> bool:
    """افزودن مقصد جدید؛ اگر وجود داشته باشد عنوان را به‌روزرسانی می‌کند."""
    _load_dests()
    cid = int(chat_id)
    for item in _DESTS["list"]:
        if int(item.get("id")) == cid:
            # فقط عنوان را به‌روزرسانی کن (اگر ارسال شده)
            if title and item.get("title") != title:
                item["title"] = title
                _save_dests()
            return False
    _DESTS["list"].append({"id": cid, "title": str(title or "")})
    if not _DESTS.get("active"):
        _DESTS["active"] = cid
    _save_dests()
    return True

def remove_destination(chat_id: int) -> bool:
    _load_dests()
    cid = int(chat_id)
    before = len(_DESTS["list"])
    _DESTS["list"] = [x for x in _DESTS["list"] if int(x.get("id")) != cid]
    if _DESTS.get("active") == cid:
        _DESTS["active"] = _DESTS["list"][0]["id"] if _DESTS["list"] else 0
    changed = len(_DESTS["list"]) != before
    if changed:
        _save_dests()
    return changed

def set_active_destination(chat_id: int) -> bool:
    _load_dests()
    cid = int(chat_id)
    if any(int(x.get("id")) == cid for x in _DESTS["list"]):
        _DESTS["active"] = cid
        _save_dests()
        return True
    return False

def get_active_destination() -> int:
    _load_dests()
    return int(_DESTS.get("active") or 0)
