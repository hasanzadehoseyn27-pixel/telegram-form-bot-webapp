from __future__ import annotations
import json
from pathlib import Path

DATA = Path("/tmp/bot_data")
ALLOWED_FILE = DATA / "allowed_channels.json"

_ALLOWED: set[int] = set()


def _load() -> None:
    global _ALLOWED
    if ALLOWED_FILE.exists():
        try:
            ids = json.loads(ALLOWED_FILE.read_text(encoding="utf-8")) or []
            _ALLOWED = {int(x) for x in ids}
        except Exception:
            pass


def _save() -> None:
    try:
        ALLOWED_FILE.write_text(json.dumps(sorted(_ALLOWED), ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def bootstrap_allowed_channels(default_id: int | None) -> None:
    _load()
    if default_id:
        _ALLOWED.add(int(default_id))
        _save()


# -- API ---------------------------------------------------------------------

def list_allowed_channels() -> list[int]:
    _load()
    return sorted(_ALLOWED)


def is_channel_allowed(chat_id: int) -> bool:
    _load()
    return int(chat_id) in _ALLOWED


def add_allowed_channel(chat_id: int) -> bool:
    _load()
    cid = int(chat_id)
    if cid in _ALLOWED:
        return False
    _ALLOWED.add(cid)
    _save()
    return True


def remove_allowed_channel(chat_id: int) -> bool:
    _load()
    cid = int(chat_id)
    if cid not in _ALLOWED:
        return False
    _ALLOWED.remove(cid)
    _save()
    return True
