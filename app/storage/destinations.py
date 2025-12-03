from __future__ import annotations
import json
from pathlib import Path

DATA = Path("/tmp/bot_data")
DESTS_FILE = DATA / "destinations.json"

_DESTS: dict = {"list": [], "active": 0}


def _load() -> None:
    global _DESTS
    if DESTS_FILE.exists():
        try:
            _DESTS = json.loads(DESTS_FILE.read_text(encoding="utf-8")) or _DESTS
        except Exception:
            pass


def _save() -> None:
    try:
        DESTS_FILE.write_text(json.dumps(_DESTS, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def bootstrap_destinations(default_id: int, default_title: str = "") -> None:
    _load()
    if not _DESTS["list"] and default_id:
        _DESTS["list"].append({"id": int(default_id), "title": str(default_title)})
    if not _DESTS.get("active") and default_id:
        _DESTS["active"] = int(default_id)
    _save()


# -- API ---------------------------------------------------------------------

def list_destinations() -> list[dict]:
    _load()
    return list(_DESTS.get("list", []))


def add_destination(chat_id: int, title: str = "") -> bool:
    _load()
    cid = int(chat_id)
    for it in _DESTS["list"]:
        if int(it.get("id")) == cid:
            if title and it.get("title") != title:
                it["title"] = title
                _save()
            return False
    _DESTS["list"].append({"id": cid, "title": str(title)})
    if not _DESTS.get("active"):
        _DESTS["active"] = cid
    _save()
    return True


def get_active_destination() -> int:
    _load()
    return int(_DESTS.get("active") or 0)


def get_active_id_and_title() -> tuple[int, str]:
    _load()
    aid = int(_DESTS.get("active") or 0)
    title = next((it.get("title") or "" for it in _DESTS["list"] if int(it["id"]) == aid), "")
    return aid, title
