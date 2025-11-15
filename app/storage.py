from __future__ import annotations
import json
from pathlib import Path
from datetime import date

# ریشه پروژه
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DAILY_FILE  = DATA / "daily.json"
ADMINS_FILE = DATA / "admins.json"
DEST_FILE   = DATA / "destinations.json"  # {"list":[{"id":-100..., "name":"..."},...], "active":-100...}

# ---------- شماره روزانه ----------
def next_daily_number() -> tuple[int, str]:
    today = date.today().isoformat()
    data = {"date": today, "num": 0}
    if DAILY_FILE.exists():
        try: data = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    if data.get("date") != today:
        data = {"date": today, "num": 0}
    data["num"] = int(data.get("num", 0)) + 1
    DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data["num"], today

# ---------- ادمین‌ها ----------
_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0

def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
    global _ADMIN_SET, _OWNER_ID
    _OWNER_ID = int(owner_id or 0)
    saved: set[int] = set()
    if ADMINS_FILE.exists():
        try: saved = set(json.loads(ADMINS_FILE.read_text(encoding="utf-8")) or [])
        except Exception: saved = set()
    _ADMIN_SET = set(initial_env_admins or set()) | saved
    if _OWNER_ID: _ADMIN_SET.add(_OWNER_ID)
    _persist_admins()

def _persist_admins()->None:
    ADMINS_FILE.write_text(json.dumps(sorted(_ADMIN_SET), ensure_ascii=False), encoding="utf-8")

def list_admins()->list[int]:
    return sorted(_ADMIN_SET)

def add_admin(uid:int)->bool:
    uid = int(uid)
    if uid in _ADMIN_SET: return False
    _ADMIN_SET.add(uid); _persist_admins(); return True

def remove_admin(uid:int)->bool:
    uid = int(uid)
    if uid == _OWNER_ID: return False
    if uid in _ADMIN_SET:
        _ADMIN_SET.remove(uid); _persist_admins(); return True
    return False

def is_admin(uid:int)->bool:
    return int(uid) in _ADMIN_SET

# ---------- مقصدها ----------
def _read_dest()->dict:
    if DEST_FILE.exists():
        try: return json.loads(DEST_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {"list": [], "active": None}

def _write_dest(obj:dict)->None:
    DEST_FILE.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

def add_destination(chat_id:int, name:str)->bool:
    obj = _read_dest()
    ids = {int(x["id"]) for x in obj["list"]}
    chat_id = int(chat_id)
    if chat_id in ids: return False
    obj["list"].append({"id": chat_id, "name": name or str(chat_id)})
    _write_dest(obj); return True

def list_destinations()->list[tuple[int,str]]:
    obj = _read_dest()
    return [(int(x["id"]), x.get("name") or str(x["id"])) for x in obj["list"]]

def get_active_destination(fallback:int|None=None)->int|None:
    obj = _read_dest()
    act = obj.get("active")
    if act: return int(act)
    return int(fallback) if fallback else None

def set_active_destination(chat_id:int)->None:
    obj = _read_dest()
    obj["active"] = int(chat_id)
    _write_dest(obj)

def get_active_id_and_title(fallback:int|None=None)->tuple[int|None,str]:
    act = get_active_destination(fallback)
    if act is None: return None, ""
    for cid, name in list_destinations():
        if cid == act: return act, name
    return act, ""
