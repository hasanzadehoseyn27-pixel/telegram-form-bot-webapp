from __future__ import annotations
import json
from pathlib import Path
from datetime import date

# ==========================
#  مسیر داده‌ها (سازگار با لیارا)
# ==========================
DATA = Path("/tmp/bot_data")
DATA.mkdir(parents=True, exist_ok=True)

DAILY_FILE = DATA / "daily.json"               # شمارنده‌ی سراسری آگهی
ADMINS_FILE = DATA / "admins.json"             # لیست ادمین‌ها
DESTS_FILE = DATA / "destinations.json"        # لیست مقصدها (سازگاری قدیمی)
ALLOWED_FILE = DATA / "allowed_channels.json"  # لیست کانال/گروه‌های مجاز ربات
REQUIRED_FILE = DATA / "required_channels.json"  # «کانال‌های من» (عضویت اجباری کاربران عادی)

# ==========================
#  شماره آگهی
# ==========================
def next_daily_number() -> tuple[int, str]:
    today = date.today().isoformat()
    data = {"date": today, "num": 0}

    if DAILY_FILE.exists():
        try:
            data = json.loads(DAILY_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {"date": today, "num": 0}

    data["num"] = int(data.get("num", 0)) + 1
    data["date"] = today
    try:
        DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return data["num"], today

# ==========================
#  ادمین‌ها
# ==========================
_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0

def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
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
    try:
        ADMINS_FILE.write_text(
            json.dumps(sorted(_ADMIN_SET), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

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

def get_owner_id() -> int:
    return _OWNER_ID

def is_owner(uid: int) -> bool:
    return int(uid) == _OWNER_ID

# ==========================
#  مقصدها (سازگاری قدیمی)
# ==========================
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
    try:
        DESTS_FILE.write_text(json.dumps(_DESTS, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def bootstrap_destinations(default_id: int, default_title: str = "") -> None:
    _load_dests()
    if not _DESTS["list"] and default_id:
        _DESTS["list"].append({"id": int(default_id), "title": str(default_title or "")})
    if not _DESTS.get("active") and default_id:
        _DESTS["active"] = int(default_id)
    _save_dests()

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

def list_destinations() -> list[dict]:
    _load_dests()
    return list(_DESTS.get("list", []))

def get_active_destination(*_args, **_kwargs) -> int:
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

# ==========================
#  کانال‌های مجاز ارسال
# ==========================
_ALLOWED_CHANNELS: set[int] = set()

def _load_allowed() -> None:
    global _ALLOWED_CHANNELS
    if ALLOWED_FILE.exists():
        try:
            ids = json.loads(ALLOWED_FILE.read_text(encoding="utf-8")) or []
            _ALLOWED_CHANNELS = {int(x) for x in ids if isinstance(x, (int, str))}
        except Exception:
            _ALLOWED_CHANNELS = set()
    else:
        _ALLOWED_CHANNELS = set()

def _save_allowed() -> None:
    try:
        ALLOWED_FILE.write_text(
            json.dumps(sorted(_ALLOWED_CHANNELS), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

def bootstrap_allowed_channels(default_channel_id: int | None) -> None:
    _load_allowed()
    if default_channel_id:
        _ALLOWED_CHANNELS.add(int(default_channel_id))
        _save_allowed()

def list_allowed_channels() -> list[int]:
    _load_allowed()
    return sorted(_ALLOWED_CHANNELS)

def is_channel_allowed(chat_id: int) -> bool:
    _load_allowed()
    return int(chat_id) in _ALLOWED_CHANNELS

def add_allowed_channel(chat_id: int) -> bool:
    _load_allowed()
    cid = int(chat_id)
    if cid in _ALLOWED_CHANNELS:
        return False
    _ALLOWED_CHANNELS.add(cid)
    _save_allowed()
    return True

def remove_allowed_channel(chat_id: int) -> bool:
    _load_allowed()
    cid = int(chat_id)
    if cid not in _ALLOWED_CHANNELS:
        return False
    _ALLOWED_CHANNELS.remove(cid)
    _save_allowed()
    return True

# ==========================
#  «کانال‌های من» (عضویت اجباری کاربران عادی)
# ==========================
_REQUIRED_CHANNELS: list[dict] = []

def _load_required() -> None:
    global _REQUIRED_CHANNELS
    if REQUIRED_FILE.exists():
        try:
            raw = json.loads(REQUIRED_FILE.read_text(encoding="utf-8")) or []
        except Exception:
            raw = []
        items: list[dict] = []
        for it in raw:
            if isinstance(it, dict) and "id" in it:
                items.append({
                    "id": int(it.get("id")),
                    "title": str(it.get("title") or ""),
                    "username": str(it.get("username") or "").lstrip("@"),
                })
            elif isinstance(it, (int, str)):
                try:
                    cid = int(it)
                    items.append({"id": cid, "title": "", "username": ""})
                except Exception:
                    continue
        _REQUIRED_CHANNELS = items
    else:
        _REQUIRED_CHANNELS = []

def _save_required() -> None:
    try:
        REQUIRED_FILE.write_text(
            json.dumps(_REQUIRED_CHANNELS, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

def bootstrap_required_channels(default_channel_id: int | None, default_title: str = "", default_username: str = "") -> None:
    _load_required()
    if not default_channel_id:
        _save_required()
        return
    cid = int(default_channel_id)
    for ch in _REQUIRED_CHANNELS:
        try:
            if int(ch.get("id")) == cid:
                if default_title and not ch.get("title"):
                    ch["title"] = str(default_title)
                if default_username and not ch.get("username"):
                    ch["username"] = str(default_username).lstrip("@")
                _save_required()
                return
        except Exception:
            continue
    _REQUIRED_CHANNELS.append({
        "id": cid,
        "title": str(default_title or ""),
        "username": str(default_username or "").lstrip("@"),
    })
    _save_required()

def list_required_channels() -> list[dict]:
    _load_required()
    return list(_REQUIRED_CHANNELS)

def get_required_channel_ids() -> list[int]:
    _load_required()
    ids: list[int] = []
    for ch in _REQUIRED_CHANNELS:
        try:
            ids.append(int(ch.get("id")))
        except Exception:
            continue
    return ids

def add_required_channel(chat_id: int, title: str = "", username: str = "") -> bool:
    _load_required()
    cid = int(chat_id)
    uname = str(username or "").lstrip("@")
    for ch in _REQUIRED_CHANNELS:
        try:
            if int(ch.get("id")) == cid:
                changed = False
                if title and ch.get("title") != title:
                    ch["title"] = str(title)
                    changed = True
                if uname and ch.get("username") != uname:
                    ch["username"] = uname
                    changed = True
                if changed:
                    _save_required()
                return False
        except Exception:
            continue
    _REQUIRED_CHANNELS.append({
        "id": cid,
        "title": str(title or ""),
        "username": uname,
    })
    _save_required()
    return True

def remove_required_channel(chat_id: int) -> bool:
    _load_required()
    cid = int(chat_id)
    idx = None
    for i, ch in enumerate(_REQUIRED_CHANNELS):
        try:
            if int(ch.get("id")) == cid:
                idx = i
                break
        except Exception:
            continue
    if idx is None:
        return False
    _REQUIRED_CHANNELS.pop(idx)
    _save_required()
    return True
