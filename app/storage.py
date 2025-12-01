from __future__ import annotations
import json
from pathlib import Path
from datetime import date

# مسیر داده‌ها – تنها مسیر قابل نوشتن در لیارا
DATA = Path("/var/lib/data/bot_data")
DATA.mkdir(parents=True, exist_ok=True)

DAILY_FILE = DATA / "daily.json"
ADMINS_FILE = DATA / "admins.json"
DESTS_FILE = DATA / "destinations.json"
ACCESS_FILE = DATA / "access.json"  # دسترسی ادمین‌ها به گروه/کانال‌ها

# ---------- شماره روزانه ----------
def next_daily_number() -> tuple[int, str]:
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

# ---------- ادمین‌ها (پایدار) ----------
_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0


def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
    """در شروع برنامه: ادمین‌های .env + فایل + OWNER"""
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
        return False
    if uid in _ADMIN_SET:
        _ADMIN_SET.remove(uid)
        _persist_admins()
        return True
    return False


def is_admin(uid: int) -> bool:
    return int(uid) in _ADMIN_SET


def is_owner(uid: int) -> bool:
    """OWNER همان کسی است که در .env به عنوان OWNER_ID تنظیم شده است."""
    return int(uid) == int(_OWNER_ID or 0)


def get_owner_id() -> int:
    return int(_OWNER_ID or 0)

# ---------- مقصدها (گروه/کانال پیش‌فرض ارسال آگهی) ----------
# ساختار فایل:
# {"list":[{"id":-1001,"title":"گروه A"}, …], "active":-1001}
_DESTS: dict = {"list": [], "active": 0}


def _load_dests() -> None:
    global _DESTS
    if DESTS_FILE.exists():
        try:
            _DESTS = json.loads(DESTS_FILE.read_text(encoding="utf-8")) or {
                "list": [],
                "active": 0,
            }
        except Exception:
            _DESTS = {"list": [], "active": 0}
    else:
        _DESTS = {"list": [], "active": 0}


def _save_dests() -> None:
    DESTS_FILE.write_text(json.dumps(_DESTS, ensure_ascii=False), encoding="utf-8")


def bootstrap_destinations(default_id: int, default_title: str = "") -> None:
    _load_dests()
    if not _DESTS["list"] and default_id:
        _DESTS["list"].append(
            {"id": int(default_id), "title": str(default_title or "")}
        )
    if not _DESTS.get("active") and default_id:
        _DESTS["active"] = int(default_id)
    _save_dests()


def list_destinations() -> list[dict]:
    _load_dests()
    return list(_DESTS.get("list", []))


def add_destination(chat_id: int, title: str = "") -> bool:
    _load_dests()
    cid = int(chat_id)
    for item in _DESTS["list"]:
        if int(item.get("id")) == cid:
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


def get_active_destination(*_args, **_kwargs) -> int:
    """ID مقصد فعال (سازگار با امضای قدیمی که اشتباهی آرگومان می‌دادند)."""
    _load_dests()
    return int(_DESTS.get("active") or 0)


def get_active_id_and_title() -> tuple[int, str]:
    _load_dests()
    aid = int(_DESTS.get("active") or 0)
    title = ""
    for it in _DESTS.get("list", []):
        if int(it.get("id")) == aid:
            title = it.get("title") or ""
            break
    return aid, title

# ---------- مدیریت دسترسی ادمین‌ها به گروه/کانال‌ها ----------
# ساختار فایل access.json:
# {
#   "471877764": [-1001234567890, -100987654321],
#   "111222333": [-10011223344]
# }

_ACCESS: dict[int, set[int]] = {}


def _load_access() -> None:
    global _ACCESS
    if not ACCESS_FILE.exists():
        _ACCESS = {}
        return
    try:
        raw = json.loads(ACCESS_FILE.read_text(encoding="utf-8") or "{}")
    except Exception:
        raw = {}
    acc: dict[int, set[int]] = {}
    for k, v in (raw or {}).items():
        try:
            uid = int(k)
        except Exception:
            continue
        chats = set()
        for cid in v or []:
            try:
                chats.add(int(cid))
            except Exception:
                continue
        if chats:
            acc[uid] = chats
    _ACCESS = acc


def _save_access() -> None:
    raw = {str(uid): sorted(list(chats)) for uid, chats in _ACCESS.items()}
    ACCESS_FILE.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def list_access_for_admin(uid: int) -> list[int]:
    """لیست chat_id هایی که این ادمین روی آن‌ها دسترسی دارد."""
    _load_access()
    return sorted(list(_ACCESS.get(int(uid), set())))


def add_access_for_admin(uid: int, chat_id: int) -> bool:
    """یک chat_id جدید برای این ادمین ثبت می‌کند. اگر قبلاً بوده False برمی‌گرداند."""
    _load_access()
    uid = int(uid)
    chat_id = int(chat_id)
    chats = _ACCESS.setdefault(uid, set())
    if chat_id in chats:
        return False
    chats.add(chat_id)
    _save_access()
    return True


def remove_access_for_admin(uid: int, chat_id: int) -> bool:
    """یک chat_id را از دسترسی‌های ادمین حذف می‌کند."""
    _load_access()
    uid = int(uid)
    chat_id = int(chat_id)
    chats = _ACCESS.get(uid)
    if not chats or chat_id not in chats:
        return False
    chats.remove(chat_id)
    if not chats:
        _ACCESS.pop(uid, None)
    _save_access()
    return True


def has_access(uid: int, chat_id: int) -> bool:
    """آیا این ادمین روی این chat_id دسترسی دارد؟"""
    _load_access()
    return int(chat_id) in _ACCESS.get(int(uid), set())
