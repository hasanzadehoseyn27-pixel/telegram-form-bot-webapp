from __future__ import annotations
import json
from pathlib import Path
from datetime import date

# ریشه پروژه = پوشه‌ی بالای app/
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DAILY_FILE  = DATA / "daily.json"
ADMINS_FILE = DATA / "admins.json"
DESTS_FILE  = DATA / "dests.json"

# --------- شماره‌ی روزانه آگهی ---------
def next_daily_number() -> tuple[int, str]:
    """برمی‌گرداند: (شماره‌ی امروز, تاریخ میلادی ISO) و ذخیره می‌کند."""
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
    """ابتدای برنامه یک‌بار فراخوانی شود."""
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
    ADMINS_FILE.write_text(json.dumps(sorted(_ADMIN_SET), ensure_ascii=False), encoding="utf-8")

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
        return False
    if uid in _ADMIN_SET:
        _ADMIN_SET.remove(uid)
        _persist_admins()
        return True
    return False

def is_admin(uid: int) -> bool:
    return int(uid) in _ADMIN_SET

# --------- مقاصد انتشار (چند گروه/کانال) ---------
# ساختار فایل:
# {"active": -100123..., "items": [{"id": -100123..., "title": "My Channel"}, ...]}
def _read_dests_raw() -> dict:
    if DESTS_FILE.exists():
        try:
            return json.loads(DESTS_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}

def _write_dests_raw(doc: dict) -> None:
    DESTS_FILE.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

def bootstrap_dests(initial_target_id: int|None) -> None:
    """اگر مقصدی نداریم و env مقدار داشت، همان را به عنوان مقصد فعال ثبت کند."""
    doc = _read_dests_raw()
    items = doc.get("items") or []
    if not items and initial_target_id:
        doc = {"active": int(initial_target_id), "items": [{"id": int(initial_target_id), "title": ""}]}
        _write_dests_raw(doc)

def list_dests() -> list[dict]:
    doc = _read_dests_raw()
    return doc.get("items") or []

def get_active_dest() -> int:
    doc = _read_dests_raw()
    return int(doc.get("active") or 0)

def set_active_dest(chat_id: int) -> bool:
    doc = _read_dests_raw()
    items = doc.get("items") or []
    ids = {int(it["id"]) for it in items}
    if int(chat_id) not in ids:
        return False
    doc["active"] = int(chat_id)
    _write_dests_raw(doc)
    return True

def add_dest(chat_id: int, title: str = "") -> bool:
    chat_id = int(chat_id)
    doc = _read_dests_raw()
    items = doc.get("items") or []
    ids = {int(it["id"]) for it in items}
    if chat_id in ids:
        return False
    items.append({"id": chat_id, "title": title or ""})
    doc["items"] = items
    if not doc.get("active"):
        doc["active"] = chat_id
    _write_dests_raw(doc)
    return True

def remove_dest(chat_id: int) -> bool:
    chat_id = int(chat_id)
    doc = _read_dests_raw()
    items = doc.get("items") or []
    new_items = [it for it in items if int(it["id"]) != chat_id]
    if len(new_items) == len(items):
        return False
    doc["items"] = new_items
    if int(doc.get("active") or 0) == chat_id:
        doc["active"] = new_items[0]["id"] if new_items else 0
    _write_dests_raw(doc)
    return True
