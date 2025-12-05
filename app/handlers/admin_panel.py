from __future__ import annotations
import re

from aiogram import Router, types, F

from ..config import SETTINGS
from ..keyboards import (
    admin_root_kb,
    admin_admins_kb,
    admin_allowed_kb,
    admin_my_channels_kb,
    start_keyboard,           # ← اضافه شد برای برگشت به منوی اصلی
)
from ..storage import (
    list_admins, add_admin, remove_admin, is_admin, is_owner,
    list_allowed_channels, add_allowed_channel, remove_allowed_channel,
    list_required_channels, add_required_channel, remove_required_channel,
    add_destination,
)
from .state import ADMIN_WAIT_INPUT, ACCESS_CH_WAIT, MEMBERS_CH_WAIT

router = Router()

# --------------------------------------------------------------------------- #
#                              کمکى‌ها / Helpers                              #
# --------------------------------------------------------------------------- #

def _extract_public_tme_username_from_link(text: str) -> str | None:
    """
    فقط لینک‌های عمومی t.me/username را می‌پذیریم.
    joinchat/+ و t.me/c/... پشتیبانی نمی‌شوند.
    خروجی نمونه: '@username'
    """
    t = (text or "").strip()
    m = re.search(r"(?:https?://)?t\.me/([^ \n]+)", t)
    if not m:
        return None
    slug = m.group(1).split("?")[0].strip()
    if slug.startswith("+") or slug.startswith("joinchat/") or slug.startswith("c/"):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]{5,}", slug):
        return None
    return "@" + slug.lstrip("@")

# --------------------------------------------------------------------------- #
#                             ریشهٔ پنل مدیریتی                               #
# --------------------------------------------------------------------------- #

@router.message(F.text == "⚙️ پنل مدیریتی")
async def admin_panel_root_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    kb = admin_root_kb(is_owner(message.from_user.id))
    await message.answer("پنل مدیریتی:", reply_markup=kb)


# 🔙 این دکمه را در *منوی پنل مدیریتی* می‌زنیم تا برگردیم به منوی اصلی استارت
@router.message(F.text == "🔙 بازگشت")
async def admin_back_to_main_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است.")
        return
    kb = start_keyboard(SETTINGS.WEBAPP_URL, True)
    await message.answer("بازگشت به منوی اصلی ربات:", reply_markup=kb)


# این دکمه در زیرمنوها است (ادمین‌ها، کانال‌های مجاز، کانال‌های من)
# و فقط کاربر را به خودِ پنل مدیریتی برمی‌گرداند
@router.message(F.text == "🔙 بازگشت به پنل")
async def admin_back_to_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    kb = admin_root_kb(is_owner(message.from_user.id))
    await message.answer("بازگشت به پنل مدیریتی.", reply_markup=kb)

# --------------------------------------------------------------------------- #
#                           بخش «ادمین‌ها»                                   #
# --------------------------------------------------------------------------- #

@router.message(F.text == "👤 مدیریت ادمین‌ها")
async def admin_manage_admins_root(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    kb = admin_admins_kb()
    await message.answer("مدیریت ادمین‌ها:", reply_markup=kb)

@router.message(F.text == "📋 لیست ادمین‌ها")
async def admin_list_msg(message: types.Message):
    """
    فهرست ادمین‌ها را با شکل زیر می‌فرستد:
        123456789  —  @username
    یا اگر کاربر username ندارد:
        123456789  —  Ali Rezaei
    و اگر خطا در واکشی رخ دهد فقط آیدی نمایش داده می‌شود.
    """
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return

    admins = list_admins()
    if not admins:
        await message.answer("— خالی —")
        return

    lines = ["ادمین‌های فعلی:"]
    for uid in admins:
        try:
            chat = await message.bot.get_chat(uid)
            uname = getattr(chat, "username", "") or ""
            full  = getattr(chat, "full_name", "") or getattr(chat, "first_name", "")
            extra = f"@{uname}" if uname else full
            lines.append(f"{uid}  —  {extra}" if extra else str(uid))
        except Exception:
            lines.append(str(uid))

    await message.answer("\n".join(lines))

@router.message(F.text == "➕ افزودن ادمین")
async def admin_add_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "add"}
    await message.answer(
        "آیدی عددی کاربر را ارسال کنید، یا یکی از موارد زیر:\n"
        "• @username کاربر\n"
        "• لینک t.me/username\n"
        "• یا پیام کاربر را برای من فوروارد کنید."
    )

@router.message(F.text == "🗑 حذف ادمین")
async def admin_remove_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "remove"}
    await message.answer(
        "برای حذف ادمین، یکی از موارد زیر را بفرستید:\n"
        "• آیدی عددی ادمین\n"
        "• @username ادمین\n"
        "• لینک t.me/username\n"
        "• یا پیام ادمین را برای من فوروارد کنید."
    )

@router.message(F.text, F.from_user.id.func(lambda uid: uid in ADMIN_WAIT_INPUT))
async def admin_id_input(message: types.Message):
    """
    دریافت ورودی برای افزودن/حذف ادمین:
      - آیدی عددی (123456789)
      - @username
      - لینک t.me/username
      - یا فوروارد کردن پیام کاربر
    """
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w or not is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip()
    uid: int | None = None

    # 1) اگر پیام را از آن کاربر فوروارد کرده باشد → از forward_from.id استفاده کن
    if message.forward_from:
        uid = message.forward_from.id

    # 2) اگر ورودی فقط عدد بود → همان آیدی عددی
    if uid is None and re.fullmatch(r"\d{4,}", raw):
        uid = int(raw)

    # 3) اگر چیزی شبیه @username یا لینک t.me/username فرستاد
    username: str | None = None
    if uid is None:
        # حالت @username
        m = re.search(r"@([A-Za-z0-9_]{5,})", raw)
        if not m:
            # حالت لینک t.me/username
            m = re.search(r"(?:https?://)?t\.me/([^ \n]+)", raw)
        if m:
            username = m.group(1).split("?")[0].lstrip("@")

    if uid is None and username:
        try:
            chat = await message.bot.get_chat(username)
            uid = chat.id
        except Exception:
            uid = None

    # اگر هنوز نتوانستیم uid را به‌دست بیاوریم → پیام راهنما
    if uid is None:
        await message.reply(
            "ورودی نامعتبر است.\n"
            "لطفاً یکی از موارد زیر را بفرستید:\n"
            "• آیدی عددی کاربر (مثلاً 123456789)\n"
            "• @username کاربر\n"
            "• لینک t.me/username\n"
            "• یا پیام کاربر را برای من فوروارد کنید."
        )
        # state را نگه می‌داریم تا دوباره تلاش کند
        return

    mode = w["mode"]
    if mode == "add":
        ok = add_admin(uid)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")
    elif mode == "remove":
        ok = remove_admin(uid)
        await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف نیست/یافت نشد.")

    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

# --------------------------------------------------------------------------- #
#                       بخش «کانال‌های مجاز ارسال» (OWNER)                   #
# --------------------------------------------------------------------------- #

@router.message(F.text == "📡 مدیریت کانال‌های مجاز")
async def admin_manage_allowed_root(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer(
            "⛔ شما در حال حاضر به این بخش دسترسی ندارید.\nبرای فعال‌سازی دسترسی، با مدیر اصلی هماهنگ کنید."
        )
        return
    kb = admin_allowed_kb()
    await message.answer("مدیریت کانال‌ها و گروه‌های مجاز:", reply_markup=kb)

@router.message(F.text == "📋 لیست کانال‌های مجاز")
async def list_allowed_channels_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    ids = list_allowed_channels()
    if not ids:
        await message.answer("هیچ کانال/گروه مجازی ثبت نشده است.")
        return
    lines = ["کانال‌ها/گروه‌های مجاز ربات:"]
    for cid in ids:
        flag = " (کانال اصلی)" if int(cid) == int(SETTINGS.TARGET_GROUP_ID) else ""
        lines.append(f"- {cid}{flag}")
    await message.answer("\n".join(lines))

@router.message(F.text == "➕ افزودن کانال مجاز")
async def add_allowed_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    ACCESS_CH_WAIT[message.from_user.id] = {"mode": "add"}
    await message.answer("لطفاً لینک عمومی کانال/گروه را بفرستید (مثال: https://t.me/testchannel).")

@router.message(F.text == "🗑 حذف کانال مجاز")
async def remove_allowed_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    ACCESS_CH_WAIT[message.from_user.id] = {"mode": "remove"}
    await message.answer("لطفاً لینک عمومی کانال/گروه برای حذف را بفرستید (مثال: https://t.me/testchannel).")

@router.message(F.text, F.from_user.id.func(lambda uid: uid in ACCESS_CH_WAIT))
async def access_channel_flow(message: types.Message):
    st = ACCESS_CH_WAIT.get(message.from_user.id)
    if not st:
        return

    ref = _extract_public_tme_username_from_link(message.text)
    if not ref:
        await message.reply(
            "❗ فقط لینک عمومی t.me/username پشتیبانی می‌شود.\n"
            "اگر کانال خصوصی است یا لینک joinchat/+ دارد، ابتدا آن را عمومی کنید."
        )
        return

    try:
        chat = await message.bot.get_chat(ref)
        cid = chat.id
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "") or ""
    except Exception:
        await message.reply("❌ ربات نتوانست اطلاعات کانال را بگیرد.\nمطمئن شوید داخل کانال عضو است و یوزرنیم عمومی دارد.")
        return

    mode = st["mode"]
    if mode == "add":
        ok = add_allowed_channel(cid)
        if ok:
            add_destination(cid, title)  # برای ثبت عنوان
            await message.reply(f"✅ کانال مجاز اضافه شد.\nchat_id: {cid}\nعنوان: {title or ref}")
        else:
            await message.reply("ℹ️ این کانال قبلاً در لیست بود.")
    elif mode == "remove":
        if int(cid) == int(SETTINGS.TARGET_GROUP_ID):
            await message.reply("⛔ امکان حذف «کانال اصلی» وجود ندارد.")
        else:
            ok = remove_allowed_channel(cid)
            await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین کانالی در لیست نبود.")
    ACCESS_CH_WAIT.pop(message.from_user.id, None)

# --------------------------------------------------------------------------- #
#                      بخش «کانال‌های من» (عضویت اجباری)                     #
# --------------------------------------------------------------------------- #

@router.message(F.text == "📣 کانال‌های من")
async def admin_my_channels_root(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    kb = admin_my_channels_kb()
    await message.answer("مدیریت کانال‌هایی که عضویت کاربران عادی در آن‌ها الزامی است:", reply_markup=kb)

@router.message(F.text == "📋 لیست کانال‌های من")
async def list_my_channels_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    items = list_required_channels()
    if not items:
        await message.answer("هنوز هیچ کانالی ثبت نشده است.")
        return
    lines = ["کانال‌هایی که عضویت در آن‌ها برای کاربران عادی الزامی است:"]
    for ch in items:
        cid = int(ch["id"])
        title = ch.get("title") or ""
        username = ch.get("username") or ""
        extras = [f"@{username}"] if username else []
        if cid == int(SETTINGS.TARGET_GROUP_ID):
            extras.append("کانال اصلی")
        suffix = (" - " + " • ".join(extras)) if extras else ""
        lines.append(f"- {cid}{' - ' + title if title else ''}{suffix}")
    await message.answer("\n".join(lines))

@router.message(F.text == "➕ افزودن کانال من")
async def add_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "add"}
    await message.answer("لطفاً لینک عمومی کانال/گروه را بفرستید (مثال: https://t.me/testchannel).")

@router.message(F.text == "🗑 حذف کانال من")
async def remove_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return
    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "remove"}
    await message.answer("لطفاً لینک عمومی کانال/گروه برای حذف را بفرستید (مثال: https://t.me/testchannel).")

@router.message(F.text, F.from_user.id.func(lambda uid: uid in MEMBERS_CH_WAIT))
async def my_channels_flow(message: types.Message):
    st = MEMBERS_CH_WAIT.get(message.from_user.id)
    if not st:
        return

    ref = _extract_public_tme_username_from_link(message.text)
    if not ref:
        await message.reply(
            "❗ فقط لینک عمومی t.me/username پشتیبانی می‌شود.\nاگر خصوصی است، ابتدا کانال را عمومی کنید."
        )
        return

    try:
        chat = await message.bot.get_chat(ref)
        cid = chat.id
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "") or ""
        username = getattr(chat, "username", None) or ref.lstrip("@")
    except Exception:
        await message.reply("❌ ربات نتوانست اطلاعات کانال را بگیرد.")
        return

    mode = st["mode"]
    if mode == "add":
        ok = add_required_channel(cid, title=title, username=username)
        if ok:
            await message.reply(f"✅ اضافه شد.\nchat_id: {cid}\nعنوان: {title or username}")
        else:
            await message.reply("ℹ️ قبلاً ثبت شده بود.")
    elif mode == "remove":
        if int(cid) == int(SETTINGS.TARGET_GROUP_ID):
            await message.reply("⛔ امکان حذف «کانال اصلی» وجود ندارد.")
        else:
            ok = remove_required_channel(cid)
            await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین کانالی ثبت نشده است.")
    MEMBERS_CH_WAIT.pop(message.from_user.id, None)
