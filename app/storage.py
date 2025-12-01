# app/storage.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import date

# ==========================
#  مسیر داده‌ها (سازگار با لیارا)
# ==========================

# روی لیارا /usr/src/app و /var/lib معمولاً read-only هستند،
# اما /tmp قابل‌نوشتن است؛ پس اینجا را برای فایل‌های موقتی انتخاب می‌کنیم.
DATA = Path("/tmp/bank_khodro_bot")
DATA.mkdir(parents=True, exist_ok=True)

DAILY_FILE = DATA / "daily.json"
ADMINS_FILE = DATA / "admins.json"
DESTS_FILE = DATA / "destinations.json"
ACCESS_FILE = DATA / "access.json"  # دسترسی ادمین‌ها به مقصدها

# ==========================
#  شماره آگهی (سراسری و بدون ریست روزانه)
# ==========================

def next_daily_number() -> tuple[int, str]:
    """
    شمارنده‌ی سراسری آگهی:
      - از ۱ تا بی‌نهایت بالا می‌رود
      - با عوض شدن روز، ریست نمی‌شود
    ساختار فایل DAILY_FILE:
      {"date": "2025-12-01", "num": 123}
    """
    today = date.today().isoformat()
    data = {"date": today, "num": 0}

    if DAILY_FILE.exists():
        try:
            data = json.loads(DAILY_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {"date": today, "num": 0}

    # دیگر بر اساس تاریخ ریست نمی‌کنیم
    data["num"] = int(data.get("num", 0)) + 1
    data["date"] = today

    try:
        DAILY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        # اگر نوشتن روی دیسک شکست بخورد، فقط شمارنده‌ی حافظه‌ای را داریم
        pass

    return data["num"], today

# ==========================
#  ادمین‌ها
# ==========================

_ADMIN_SET: set[int] = set()
_OWNER_ID: int = 0


def bootstrap_admins(initial_env_admins: set[int], owner_id: int) -> None:
    """
    در شروع برنامه:
      - ادمین‌های داخل .env (ADMIN_IDS)
      - ادمین‌های ذخیره‌شده در فایل
      - OWNER_ID
    را با هم merge می‌کنیم.
    """
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
    """
    ادمین‌ها را در ADMINS_FILE می‌نویسد.
    (روی لیارا این فایل در /tmp است و با هر استارت کانتینر صفر می‌شود.)
    """
    try:
        ADMINS_FILE.write_text(
            json.dumps(sorted(_ADMIN_SET), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        # اگر نوشتن روی دیسک شکست خورد، فقط از حافظه استفاده می‌کنیم.
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
    # مالک را نمی‌توان حذف کرد
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
    """
    فقط برای چک‌کردن اینکه این کاربر همان OWNER_ID است یا نه.
    (برای منوی «مدیریت دسترسی» که فقط owner اجازه دارد.)
    """
    return int(uid) == _OWNER_ID

# ==========================
#  مقصدها (گروه/کانال)
# ==========================

# ساختار DESTS_FILE:
# {
#   "list":[{"id":-1001,"title":"گروه A"}, …],
#   "active":-1001
# }
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
    try:
        DESTS_FILE.write_text(
            json.dumps(_DESTS, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        # اگر نوشتن روی دیسک شکست بخورد، فقط حافظه فعلی را داریم.
        pass


def bootstrap_destinations(default_id: int, default_title: str = "") -> None:
    """
    در شروع برنامه، اگر هیچ مقصدی در فایل نبود، مقصد پیش‌فرض را
    از .env اضافه می‌کند و آن را active می‌گذارد.
    """
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
    """
    یک مقصد جدید (گروه/کانال) اضافه می‌کند.
    اگر قبلاً وجود داشته باشد، False برمی‌گرداند.
    """
    _load_dests()
    cid = int(chat_id)

    for item in _DESTS["list"]:
        if int(item.get("id")) == cid:
            # اگر فقط عنوان عوض شده باشد، آن را آپدیت می‌کنیم
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
    """
    مقصد را حذف می‌کند. اگر active بود، اولینِ باقی‌مانده را active می‌کند.
    """
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
    """
    مقصد فعال را روی chat_id تنظیم می‌کند، اگر در لیست باشد.
    """
    _load_dests()
    cid = int(chat_id)

    if any(int(x.get("id")) == cid for x in _DESTS["list"]):
        _DESTS["active"] = cid
        _save_dests()
        return True

    return False


def get_active_destination(*_args, **_kwargs) -> int:
    """
    برای سازگاری با امضای قدیمی که اشتباهی آرگومان می‌دادند،
    هر آرگومان اضافی را نادیده می‌گیرد.
    """
    _load_dests()
    return int(_DESTS.get("active") or 0)


def get_active_id_and_title() -> tuple[int, str]:
    """
    (chat_id, title) مقصد فعال را برمی‌گرداند.
    اگر چیزی پیدا نشود، (0, "") می‌دهد.
    """
    _load_dests()

    aid = int(_DESTS.get("active") or 0)
    title = ""

    for it in _DESTS.get("list", []):
        if int(it.get("id")) == aid:
            title = it.get("title") or ""
            break

    return aid, title

# ==========================
#  سطح دسترسی ادمین‌ها به مقصدها
# ==========================

# ساختار ACCESS_FILE:
# {
#   "471877764": [-10012345, -10098765],
#   "123456789": [-10012345]
# }
_ACCESS_MAP: dict[str, list[int]] = {}


def _load_access() -> None:
    global _ACCESS_MAP
    if ACCESS_FILE.exists():
        try:
            raw = json.loads(ACCESS_FILE.read_text(encoding="utf-8")) or {}
            # اطمینان از تبدیل به dict[str, list[int]]
            fixed: dict[str, list[int]] = {}
            for k, v in raw.items():
                try:
                    aid_str = str(int(k))
                except Exception:
                    continue
                try:
                    lst = [int(x) for x in (v or [])]
                except Exception:
                    lst = []
                fixed[aid_str] = lst
            _ACCESS_MAP = fixed
        except Exception:
            _ACCESS_MAP = {}
    else:
        _ACCESS_MAP = {}


def _save_access() -> None:
    try:
        ACCESS_FILE.write_text(
            json.dumps(_ACCESS_MAP, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        # اگر نتوانست روی دیسک بنویسد، فقط حافظه فعلی را داریم.
        pass


def list_access_for_admin(admin_id: int) -> list[int]:
    """
    لیست chat_idهایی که این ادمین اجازه‌ی دسترسی دارد.
    """
    _load_access()
    return list(_ACCESS_MAP.get(str(int(admin_id)), []) or [])


def add_access_for_admin(admin_id: int, chat_id: int) -> bool:
    """
    به یک ادمین، دسترسیِ یک مقصد (گروه/کانال) را اضافه می‌کند.
    اگر قبلاً وجود داشته باشد، False برمی‌گرداند.
    """
    _load_access()
    aid = str(int(admin_id))
    cid = int(chat_id)

    lst = _ACCESS_MAP.get(aid) or []
    if cid in lst:
        return False

    lst.append(cid)
    _ACCESS_MAP[aid] = lst
    _save_access()
    return True


def remove_access_for_admin(admin_id: int, chat_id: int) -> bool:
    """
    دسترسی یک مقصد را از یک ادمین حذف می‌کند.
    """
    _load_access()
    aid = str(int(admin_id))
    cid = int(chat_id)

    lst = _ACCESS_MAP.get(aid) or []
    if cid not in lst:
        return False

    lst = [x for x in lst if x != cid]
    if lst:
        _ACCESS_MAP[aid] = lst
    else:
        _ACCESS_MAP.pop(aid, None)

    _save_access()
    return True


def admin_has_access(admin_id: int, chat_id: int) -> bool:
    """
    کمک‌تابع: چک می‌کند آیا این ادمین اجازه‌ی دسترسی به این مقصد را دارد یا نه.
    - owner همیشه دسترسی دارد.
    - برای بقیه، فقط اگر chat_id در لیست ACCESS_MAP باشد.
    """
    if is_owner(admin_id):
        return True

    access_list = list_access_for_admin(admin_id)
    if not access_list:
        return False

    return int(chat_id) in access_list


def get_accessible_chats_for_admin(admin_id: int) -> list[int]:
    """
    برای دکمه «✅ اعمال روی پست گروه»:
      - OWNER: همه‌ی مقصدهای ثبت‌شده در DESTS_FILE
      - بقیه‌ی ادمین‌ها: فقط لیست داخل ACCESS_FILE
    """
    admin_id = int(admin_id)
    if is_owner(admin_id):
        _load_dests()
        ids = [int(x.get("id")) for x in _DESTS.get("list", []) if x.get("id")]
        return sorted({i for i in ids if i})
    else:
        return list_access_for_admin(admin_id)
