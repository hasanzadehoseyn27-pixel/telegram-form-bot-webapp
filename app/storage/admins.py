from __future__ import annotations
import json
from pathlib import Path

DATA = Path("/tmp/bot_data")
ADMINS_FILE = DATA / "admins.json"

_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0


def _persist() -> None:
    try:
        ADMINS_FILE.write_text(
            json.dumps(sorted(_ADMIN_SET), ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
    """بارگذاری اولیه از دیسک و ترکیب با ENV."""
    global _ADMIN_SET, _OWNER_ID
    _OWNER_ID = int(owner_id or 0)

    saved: set[int] = set()
    if ADMINS_FILE.exists():
        try:
            saved = set(json.loads(ADMINS_FILE.read_text(encoding="utf-8")) or [])
        except Exception:
            pass

    _ADMIN_SET = set(initial_env_admins or set()) | saved
    if _OWNER_ID:
        _ADMIN_SET.add(_OWNER_ID)
    _persist()


# -- API عمومی ---------------------------------------------------------------

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


def get_owner_id() -> int:
    return _OWNER_ID


def is_owner(uid: int) -> bool:
    return int(uid) == _OWNER_ID
