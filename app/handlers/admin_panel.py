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
#                               Helpers                                       #
# --------------------------------------------------------------------------- #

def _extract_public_tme_username_from_link(text: str) -> str | None:
    """
    قبول لینک‌های عمومی t.me/username (عمومی فقط)
    """
    t = (text or "").strip()
    m = re.search(r"(?:https?://)?t\.me/([^ \n]+)", t)
    if not m:
        return None

    slug = m.group(1).split("?")[0].strip()

    # جلوگیری از لینک‌های خصوصی
    if slug.startswith("+") or slug.startswith("joinchat/") or slug.startswith("c/"):
        return None

    # یوزرنیم معتبر 3 تا 32 کاراکتر
    if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", slug):
        return None

    return "@" + slug.lstrip("@")

# --------------------------------------------------------------------------- #
#                              Root Panel                                      #
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

    kb = start_keyboard(SETTINGS.WEBAPP_URL, True)
    await message.answer("بازگشت:", reply_markup=kb)


@router.message(F.text == "🔙 بازگشت به پنل")
async def admin_back_to_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return

    kb = admin_root_kb(is_owner(message.from_user.id))
    await message.answer("بازگشت به پنل:", reply_markup=kb)

# --------------------------------------------------------------------------- #
#                          مدیریت ادمین‌ها                                    #
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
            full = getattr(chat, "full_name", "") or getattr(chat, "first_name", "")
            extra = f"@{uname}" if uname else full
            lines.append(f"{uid} — {extra}")
        except Exception:
            lines.append(str(uid))

    await message.answer("\n".join(lines))


# ---------------------- افزودن / حذف ادمین ----------------------

@router.message(F.text == "➕ افزودن ادمین")
async def admin_add_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return

    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "add"}
    await message.answer("آیدی عددی یا @username را ارسال کنید:")


@router.message(F.text == "🗑 حذف ادمین")
async def admin_remove_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return

    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "remove"}
    await message.answer("آیدی عددی یا @username را ارسال کنید:")


@router.message(F.text, F.from_user.id.func(lambda uid: uid in ADMIN_WAIT_INPUT))
async def admin_id_or_username_input(message: types.Message):
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w:
        return

    raw = (message.text or "").strip()

    # حالت آیدی
    if re.fullmatch(r"\d{4,}", raw):
        uid = int(raw)
    else:
        uname = raw.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", uname):
            await message.reply("یوزرنیم نامعتبر است.")
            return
        try:
            chat = await message.bot.get_chat("@" + uname)
            uid = chat.id
        except Exception:
            await message.reply("❌ کاربری با این یوزرنیم یافت نشد.")
            return

    mode = w["mode"]
    if mode == "add":
        ok = add_admin(uid)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")

    elif mode == "remove":
        ok = remove_admin(uid)
        await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف نیست.")

    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

# --------------------------------------------------------------------------- #
#                   مدیریت «کانال‌های من» — عضویت اجباری                     #
# --------------------------------------------------------------------------- #

@router.message(F.text == "📣 کانال‌های من")
async def admin_my_channels_root(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")
        return

    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

    kb = admin_my_channels_kb()
    await message.answer("مدیریت کانال‌های اجباری:", reply_markup=kb)


@router.message(F.text == "📋 لیست کانال‌های من")
async def list_my_channels_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ اجازه ندارید.")
        return

    items = list_required_channels()
    if not items:
        await message.answer("هنوز هیچ کانالی ثبت نشده.")
        return

    lines = ["📌 لیست کانال‌های اجباری:"]

    for ch in items:
        cid = int(ch["id"])
        title = ch.get("title") or ""
        username = ch.get("username") or ""

        text = f"- {cid} — {title}"

        if username:
            text += f" • @{username}"

        if cid == SETTINGS.TARGET_GROUP_ID:
            text += " • کانال اصلی"

        lines.append(text)

    await message.answer("\n".join(lines))


@router.message(F.text == "➕ افزودن کانال من")
async def add_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")
        return

    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "add"}
    await message.answer("🔗 لینک کانال را بفرستید (مثال: https://t.me/testchannel)")


@router.message(F.text == "🗑 حذف کانال من")
async def remove_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")
        return

    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "remove"}
    await message.answer("🔗 لینک کانالی که باید حذف شود را ارسال کنید.")


@router.message(F.text, F.from_user.id.func(lambda uid: uid in MEMBERS_CH_WAIT))
async def my_channels_flow(message: types.Message):
    st = MEMBERS_CH_WAIT.get(message.from_user.id)
    if not st:
        return

    ref = _extract_public_tme_username_from_link(message.text)

    if not ref:
        await message.reply("❗ فقط لینک عمومی t.me/username مجاز است.")
        return

    try:
        chat = await message.bot.get_chat(ref)
        cid = chat.id
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "")
        username = getattr(chat, "username", "") or ref.lstrip("@")
    except Exception:
        await message.reply("❌ امکان دریافت اطلاعات کانال نیست.")
        return

    mode = st["mode"]

    if mode == "add":
        ok = add_required_channel(cid, title=title, username=username)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ این کانال از قبل وجود دارد.")

    elif mode == "remove":
        if cid == SETTINGS.TARGET_GROUP_ID:
            await message.reply("⛔ حذف کانال اصلی مجاز نیست.")
        else:
            ok = remove_required_channel(cid)
            await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین کانالی وجود ندارد.")

    MEMBERS_CH_WAIT.pop(message.from_user.id, None)
