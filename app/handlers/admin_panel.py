from __future__ import annotations
import re

from aiogram import Router, types, F

from ..config import SETTINGS
from ..keyboards import (
    admin_root_kb,
    admin_admins_kb,
    admin_my_channels_kb,
    start_keyboard,
)
from ..storage import (
    list_admins, add_admin, remove_admin, is_admin, is_owner,
    list_required_channels, add_required_channel, remove_required_channel,
)
from .state import ADMIN_WAIT_INPUT, MEMBERS_CH_WAIT

router = Router()

# --------------------------------------------------------------------------- #
#                              Helpers                                        #
# --------------------------------------------------------------------------- #

def _extract_public_tme_username_from_link(text: str) -> str | None:
    """
    قبول لینک‌ها به شکل:
    - https://t.me/username
    - t.me/username
    و username باید ۳ تا ۳۲ کاراکتر، شامل حروف، عدد و _
    """
    t = (text or "").strip()
    m = re.search(r"(?:https?://)?t\.me/([^ \n]+)", t)
    if not m:
        return None

    slug = m.group(1).split("?")[0].strip()

    # جلوگیری از لینک‌های خصوصی
    if slug.startswith("+") or slug.startswith("joinchat/") or slug.startswith("c/"):
        return None

    # یوزرنیم معتبر تلگرام: 3–32 کاراکتر
    if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", slug):
        return None

    return "@" + slug.lstrip("@")


# --------------------------------------------------------------------------- #
#                             ریشه پنل مدیریتی                                #
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
#                            مدیریت ادمین‌ها                                  #
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
    نمایش لیست ادمین‌ها با یوزرنیم در صورت وجود
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


# ---------- افزودن / حذف ادمین -----------

@router.message(F.text == "➕ افزودن ادمین")
async def admin_add_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return

    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "add"}
    await message.answer(
        "آیدی عددی یا یوزرنیم کاربر را ارسال کنید (مثل 123456789 یا @username):"
    )


@router.message(F.text == "🗑 حذف ادمین")
async def admin_remove_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return

    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "remove"}
    await message.answer(
        "آیدی عددی یا یوزرنیم ادمین را ارسال کنید (مثل 123456789 یا @username):"
    )


@router.message(F.text, F.from_user.id.func(lambda uid: uid in ADMIN_WAIT_INPUT))
async def admin_id_or_username_input(message: types.Message):
    """
    ورودی می‌تواند آیدی عددی یا یوزرنیم باشد.
    """
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w or not is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip()
    uid = None

    # حالت ۱ → آیدی عددی
    if re.fullmatch(r"\d{4,}", raw):
        uid = int(raw)

    else:
        # حالت ۲ → یوزرنیم
        uname = raw.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,}", uname):
            await message.reply("یوزرنیم نامعتبر است. نمونه صحیح: @myusername")
            return

        try:
            chat = await message.bot.get_chat("@" + uname)
            uid = chat.id
        except Exception:
            await message.reply("کاربری با این یوزرنیم یافت نشد.")
            return

    mode = w["mode"]

    if mode == "add":
        ok = add_admin(uid)
        await message.reply("✅ ادمین اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")

    elif mode == "remove":
        ok = remove_admin(uid)
        await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف وجود ندارد.")

    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

# --------------------------------------------------------------------------- #
#                      بخش «کانال‌های من» (عضویت اجباری)                     #
# --------------------------------------------------------------------------- #

@router.message(F.text == "📣 کانال‌های من")
async def admin_my_channels_root(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ دسترسی فقط برای مدیر اصلی مجاز است.")
        return

    kb = admin_my_channels_kb()
    await message.answer(
        "مدیریت کانال‌هایی که عضویت کاربران عادی در آن‌ها الزامی است:",
        reply_markup=kb,
    )


@router.message(F.text == "📋 لیست کانال‌های من")
async def list_my_channels_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ شما به این بخش دسترسی ندارید.")
        return

    items = list_required_channels()
    if not items:
        await message.answer("هنوز هیچ کانالی ثبت نشده است.")
        return

    lines = ["کانال‌های اجباری:"]
    for ch in items:
        cid = int(ch["id"])
        title = ch.get("title") or ""
        username = ch.get("username") or ""
        extras = [f"@{username}"] if username else []
        if cid == int(SETTINGS.TARGET_GROUP_ID):
            extras.append("کانال اصلی")
        suffix = (" • " + " • ".join(extras)) if extras else ""
        lines.append(f"- {cid} - {title}{suffix}")

    await message.answer("\n".join(lines))


@router.message(F.text == "➕ افزودن کانال من")
async def add_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")
        return

    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "add"}
    await message.answer("لینک عمومی کانال را ارسال کنید (مثال: https://t.me/testchannel)")


@router.message(F.text == "🗑 حذف کانال من")
async def remove_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")
        return

    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "remove"}
    await message.answer("لینک کانال جهت حذف را ارسال کنید.")


@router.message(F.text, F.from_user.id.func(lambda uid: uid in MEMBERS_CH_WAIT))
async def my_channels_flow(message: types.Message):
    st = MEMBERS_CH_WAIT.get(message.from_user.id)
    if not st:
        return

    ref = _extract_public_tme_username_from_link(message.text)
    if not ref:
        await message.reply("❗ فقط لینک عمومی t.me/username پشتیبانی می‌شود.")
        return

    try:
        chat = await message.bot.get_chat(ref)
        cid = chat.id
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "") or ""
        username = getattr(chat, "username", None) or ref.lstrip("@")
    except Exception:
        await message.reply("❌ نتوانستم اطلاعات کانال را دریافت کنم.")
        return

    mode = st["mode"]

    if mode == "add":
        ok = add_required_channel(cid, title=title, username=username)
        if ok:
            await message.reply(f"✅ اضافه شد.\nchat_id: {cid}\nعنوان: {title}")
        else:
            await message.reply("ℹ️ این کانال از قبل ثبت شده بود.")

    elif mode == "remove":
        if int(cid) == int(SETTINGS.TARGET_GROUP_ID):
            await message.reply("⛔ حذف کانال اصلی مجاز نیست.")
        else:
            ok = remove_required_channel(cid)
            await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین کانالی ثبت نشده.")

    MEMBERS_CH_WAIT.pop(message.from_user.id, None)
