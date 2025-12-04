from __future__ import annotations
import json
from pathlib import Path
from aiogram import Bot

DATA = Path("/tmp/bot_data")
REQUIRED_FILE = DATA / "required_channels.json"

_REQ: list[dict] = []


def _load() -> None:
    """Load required channels from file."""
    global _REQ
    if REQUIRED_FILE.exists():
        try:
            raw = json.loads(REQUIRED_FILE.read_text(encoding="utf-8")) or []
        except Exception:
            raw = []

        _REQ = [
            {
                "id": int(it.get("id")),
                "title": str(it.get("title") or ""),
                "username": str(it.get("username") or "").lstrip("@"),
            }
            for it in raw
            if isinstance(it, dict) and "id" in it
        ]


def _save() -> None:
    """Save required channels to file."""
    try:
        REQUIRED_FILE.write_text(json.dumps(_REQ, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def bootstrap_required_channels(
    default_id: int | None, *, default_title: str = "", default_username: str = ""
) -> None:
    """
    این تابع باید وجود داشته باشد چون storage/__init__.py آن را import می‌کند.
    """
    _load()
    if not default_id:
        _save()
        return

    cid = int(default_id)

    # اگر کانال اصلی قبلاً وجود ندارد، اضافه کن
    if not any(int(ch["id"]) == cid for ch in _REQ):
        _REQ.append(
            {
                "id": cid,
                "title": str(default_title),
                "username": str(default_username).lstrip("@"),
            }
        )

    _save()


# --------------------------------------------------------------------------- #
# همگام‌سازی اطلاعات واقعی کانال از تلگرام (title + username)
# --------------------------------------------------------------------------- #

async def sync_required_channels(bot: Bot) -> None:
    """
    اگر title یا username در فایل خالی باشد، از Telegram API گرفته و ذخیره می‌کند.
    """
    _load()
    changed = False

    for ch in _REQ:
        cid = int(ch["id"])

        try:
            info = await bot.get_chat(cid)
            api_title = getattr(info, "title", "") or getattr(info, "full_name", "")
            api_username = getattr(info, "username", "") or ""
        except:
            continue

        # اگر title در فایل خالی بود → از API بگیر
        if api_title and not ch.get("title"):
            ch["title"] = api_title
            changed = True

        # اگر username خالی بود → از API بگیر
        if api_username and not ch.get("username"):
            ch["username"] = api_username
            changed = True

    if changed:
        _save()


# --------------------------------------------------------------------------- #
# API اصلی
# --------------------------------------------------------------------------- #

def list_required_channels() -> list[dict]:
    _load()
    return list(_REQ)


def get_required_channel_ids() -> list[int]:
    _load()
    return [int(ch["id"]) for ch in _REQ]


def add_required_channel(chat_id: int, *, title: str = "", username: str = "") -> bool:
    _load()
    cid = int(chat_id)

    # اگر کانال موجود باشد → فقط update
    for ch in _REQ:
        if int(ch["id"]) == cid:
            changed = False
            if title and ch["title"] != title:
                ch["title"] = title
                changed = True

            if username and ch["username"] != username:
                ch["username"] = username.lstrip("@")
                changed = True

            if changed:
                _save()

            return False

    # اضافه کردن
    _REQ.append({"id": cid, "title": title, "username": username.lstrip("@")})
    _save()
    return True


def remove_required_channel(chat_id: int) -> bool:
    _load()
    cid = int(chat_id)
    idx = next((i for i, ch in enumerate(_REQ) if int(ch["id"]) == cid), None)

    if idx is None:
        return False

    _REQ.pop(idx)
    _save()
    return True
