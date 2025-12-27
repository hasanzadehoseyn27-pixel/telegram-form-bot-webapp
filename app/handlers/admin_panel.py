from __future__ import annotations
import re

from aiogram import Router, types, F

from ..config import SETTINGS
from ..keyboards import (
    admin_root_kb,
    admin_admins_kb,
    admin_allowed_kb,
    admin_my_channels_kb,
    admin_destinations_kb,
    start_keyboard,
)
from ..storage import (
    list_admins, add_admin, remove_admin, is_admin, is_owner,
    list_allowed_channels, add_allowed_channel, remove_allowed_channel,
    list_required_channels, add_required_channel, remove_required_channel,
    add_destination,
    list_destinations, set_active_destination, get_active_id_and_title, remove_destination, get_active_destination,
)
from .state import ADMIN_WAIT_INPUT, ACCESS_CH_WAIT, MEMBERS_CH_WAIT, DEST_WAIT

router = Router()

# --------------------------------------------------------------------------- #
#                             کمکى‌ها / Helpers                               #
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


@router.message(F.text == "🔙 بازگشت به پنل")
async def admin_back_to_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    kb = admin_root_kb(is_owner(message.from_user.id))
    await message.answer("بازگشت به پنل مدیریتی.", reply_markup=kb)

# --------------------------------------------------------------------------- #
#                           بخش «مدیریت ادمین‌ها»                              #
# --------------------------------------------------------------------------- #

@router.message(F.text == "👤 مدیریت ادمین‌ها")
async def admin_manage_admins_root(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    
    user_is_owner = is_owner(message.from_user.id)
    kb = admin_admins_kb(user_is_owner)
    
    await message.answer("مدیریت ادمین‌ها:", reply_markup=kb)

@router.message(F.text == "📋 لیست ادمین‌ها")
async def admin_list_msg(message: types.Message):
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
            is_own = is_owner(uid)
            tag = " 👑 (مالک اصلی)" if is_own else ""

            chat = await message.bot.get_chat(uid)
            uname = getattr(chat, "username", "") or ""
            full  = getattr(chat, "full_name", "") or getattr(chat, "first_name", "")
            extra = f"@{uname}" if uname else full
            
            lines.append(f"{uid}  —  {extra}{tag}" if extra else f"{uid}{tag}")
        except Exception:
            is_own = is_owner(uid)
            tag = " 👑 (مالک اصلی)" if is_own else ""
            lines.append(f"{uid}{tag}")

    await message.answer("\n".join(lines))

@router.message(F.text == "➕ افزودن ادمین")
async def admin_add_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ دسترسی ندارید (فقط مالک اصلی).")
        return
    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "add"}
    await message.answer("آیدی عددی کاربر را ارسال کنید تا ادمین شود:")

@router.message(F.text == "🗑 حذف ادمین")
async def admin_remove_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ دسترسی ندارید (فقط مالک اصلی).")
        return
    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "remove"}
    await message.answer("آیدی عددی ادمین را ارسال کنید تا حذف شود:")

@router.message(
    F.text.regexp(r"^\d{4,}$"),
    F.from_user.id.func(lambda uid: uid in ADMIN_WAIT_INPUT)
)
async def admin_id_input(message: types.Message):
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w or not is_owner(message.from_user.id):
        return

    uid = int(message.text.strip())
    mode = w["mode"]

    if mode == "add":
        ok = add_admin(uid)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")

    elif mode == "remove":
        ok = remove_admin(uid)
        await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف نیست/یافت نشد.")

    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)


# --------------------------------------------------------------------------- #
#                       بخش «کانال‌های مجاز ارسال» (OWNER)                     #
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
            add_destination(cid, title)
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
#                       بخش «کانال‌های من» (عضویت اجباری)                      #
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

# --------------------------------------------------------------------------- #
#                           بخش «مقصدها» (OWNER)                               #
# --------------------------------------------------------------------------- #

@router.message(F.text == "🎯 مدیریت مقصدها")
async def destinations_root(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return

    aid, title = get_active_id_and_title()
    kb = admin_destinations_kb()

    # تلاش برای دریافت یوزرنیم مقصد فعال
    extra_info = ""
    if aid:
        try:
            c = await message.bot.get_chat(aid)
            if c.username:
                extra_info = f" (@{c.username})"
        except:
            pass

    await message.answer(
        "مدیریت مقصدها:\n"
        f"مقصد فعال فعلی: {aid or '—'}{extra_info} {('— ' + title) if title else ''}",
        reply_markup=kb,
    )

@router.message(F.text == "📋 لیست مقصدها")
async def destinations_list(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return

    items = list_destinations()
    aid = get_active_destination()

    if not items:
        await message.answer("هیچ مقصدی ثبت نشده است.")
        return

    lines = ["مقصدهای ثبت‌شده:"]
    for it in items:
        cid = int(it.get("id") or 0)
        title = it.get("title") or ""
        
        # نمایش یوزرنیم کانال
        username_text = ""
        try:
            chat = await message.bot.get_chat(cid)
            uname = getattr(chat, "username", None)
            if uname:
                username_text = f" — @{uname}"
        except:
            pass
            
        flag = " ✅(فعال)" if cid == aid else ""
        lines.append(f"- {cid}{username_text}{(' — ' + title) if title else ''}{flag}")

    await message.answer("\n".join(lines))

@router.message(F.text == "➕ افزودن مقصد")
async def destinations_add_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return

    DEST_WAIT[message.from_user.id] = {"mode": "add"}
    await message.answer("لینک عمومی مقصد را بفرستید (مثال: https://t.me/testchannel).")

@router.message(F.text == "✅ انتخاب مقصد فعال")
async def destinations_set_active_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return

    DEST_WAIT[message.from_user.id] = {"mode": "set_active"}
    await message.answer("لینک عمومی مقصد را بفرستید تا به عنوان مقصد فعال انتخاب شود.")

@router.message(F.text == "🗑 حذف مقصد")
async def destinations_remove_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.")
        return

    DEST_WAIT[message.from_user.id] = {"mode": "remove"}
    await message.answer("لینک عمومی مقصد را بفرستید تا حذف شود.")

@router.message(F.text, F.from_user.id.func(lambda uid: uid in DEST_WAIT))
async def destinations_flow(message: types.Message):
    if not is_owner(message.from_user.id):
        return

    st = DEST_WAIT.get(message.from_user.id)
    if not st:
        return

    ref = _extract_public_tme_username_from_link(message.text)
    if not ref:
        await message.reply("❗ فقط لینک عمومی t.me/username پشتیبانی می‌شود.")
        return

    try:
        chat = await message.bot.get_chat(ref)
        cid = int(chat.id)
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "") or ""
    except Exception:
        await message.reply("❌ ربات نتوانست اطلاعات مقصد را بگیرد. مطمئن شوید ربات دسترسی دارد.")
        return

    mode = st.get("mode")

    if mode == "add":
        ok = add_destination(cid, title)
        await message.reply("✅ مقصد اضافه شد." if ok else "ℹ️ قبلاً وجود داشت (در صورت نیاز عنوان بروزرسانی شد).")

    elif mode == "set_active":
        ok = set_active_destination(cid)
        if ok:
            await message.reply(f"✅ مقصد فعال شد: {cid} — {title or ref}")
        else:
            add_destination(cid, title)
            ok2 = set_active_destination(cid)
            await message.reply(f"✅ مقصد فعال شد: {cid} — {title or ref}" if ok2 else "❌ خطا در فعال‌سازی مقصد.")

    elif mode == "remove":
        ok = remove_destination(cid)
        await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین مقصدی وجود نداشت.")

    DEST_WAIT.pop(message.from_user.id, None)

    # بازگشت به پنل مقصدها با نمایش اطلاعات کامل
    aid, t = get_active_id_and_title()
    extra_info = ""
    if aid:
        try:
            c = await message.bot.get_chat(aid)
            if c.username:
                extra_info = f" (@{c.username})"
        except:
            pass
            
    await message.answer(
        "مدیریت مقصدها:\n"
        f"مقصد فعال فعلی: {aid or '—'}{extra_info} {('— ' + t) if t else ''}",
        reply_markup=admin_destinations_kb(),
    )