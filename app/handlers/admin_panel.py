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
    list_admins,
    add_admin,
    remove_admin,
    is_admin,
    is_owner,
    list_required_channels,
    add_required_channel,
    remove_required_channel,
)
from .state import ADMIN_WAIT_INPUT, MEMBERS_CH_WAIT

router = Router()

# --------------------------------------------------------------------------- #
#                               Helpers                                       #
# --------------------------------------------------------------------------- #


def _extract_public_tme_username_from_link(text: str) -> str | None:
    """
    استخراج یوزرنیم عمومی از لینک‌های t.me/username
    (لینک‌های private مثل joinchat/c/… قبول نمی‌شوند)
    """
    t = (text or "").strip()
    m = re.search(r"(?:https?://)?t\.me/([^ \n]+)", t)
    if not m:
        return None

    slug = m.group(1).split("?")[0].strip()

    # لینک خصوصی یا گروه private
    if slug.startswith("+") or slug.startswith("joinchat/") or slug.startswith("c/"):
        return None

    # یوزرنیم معتبر ۳ تا ۳۲ کاراکتر
    if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", slug):
        return None

    return "@" + slug.lstrip("@")


# --------------------------------------------------------------------------- #
#                              Root Panel                                     #
# --------------------------------------------------------------------------- #


@router.message(F.text == "⚙️ پنل مدیریتی")
async def admin_panel_root_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")
    await message.answer(
        "پنل مدیریتی:",
        reply_markup=admin_root_kb(is_owner(message.from_user.id)),
    )


@router.message(F.text == "🔙 بازگشت")
async def admin_back_to_main_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")
    await message.answer(
        "بازگشت:",
        reply_markup=start_keyboard(SETTINGS.WEBAPP_URL, True),
    )


@router.message(F.text == "🔙 بازگشت به پنل")
async def admin_back_to_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")
    await message.answer(
        "بازگشت به پنل:",
        reply_markup=admin_root_kb(is_owner(message.from_user.id)),
    )


# --------------------------------------------------------------------------- #
#                          مدیریت ادمین‌ها                                    #
# --------------------------------------------------------------------------- #


@router.message(F.text == "👤 مدیریت ادمین‌ها")
async def admin_manage_admins_root(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")
    await message.answer("مدیریت ادمین‌ها:", reply_markup=admin_admins_kb())


@router.message(F.text == "📋 لیست ادمین‌ها")
async def admin_list_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")

    admins = list_admins()
    if not admins:
        return await message.answer("— هیچ ادمینی ثبت نشده —")

    lines = ["📌 ادمین‌های فعلی:"]

    for uid in admins:
        try:
            chat = await message.bot.get_chat(uid)
            username = getattr(chat, "username", "") or ""
            full_name = (
                getattr(chat, "full_name", "")
                or getattr(chat, "first_name", "")
                or "بدون نام"
            )

            if username:
                # @username (نام)
                lines.append(f"@{username} ({full_name})")
            else:
                lines.append(f"{full_name} (بدون یوزرنیم)")

        except Exception:
            lines.append(f"{uid} (خطا در دریافت اطلاعات)")

    await message.answer("\n".join(lines))


# ---------------------- افزودن / حذف ادمین ----------------------


@router.message(F.text == "➕ افزودن ادمین")
async def admin_add_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")

    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "add"}
    await message.answer(
        "آیدی عددی یا @username ادمین جدید را ارسال کنید.\n"
        "مثال: 5015455098 یا @ExampleUser"
    )


@router.message(F.text == "🗑 حذف ادمین")
async def admin_remove_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ دسترسی ندارید.")

    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "remove"}
    await message.answer(
        "آیدی عددی یا @username ادمینی که باید حذف شود را ارسال کنید.\n"
        "مثال: 5015455098 یا @ExampleUser"
    )


@router.message(F.text, F.from_user.id.func(lambda uid: uid in ADMIN_WAIT_INPUT))
async def admin_id_or_username_input(message: types.Message):
    """
    در این حالت فقط وقتی متن واقعا شبیه آیدی عددی یا @username باشد
    پردازش می‌کنیم. اگر نه، کاری نمی‌کنیم تا بقیه هندلرها (مثلاً دکمه‌ها)
    کار کنند.
    """
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w:
        return

    raw = (message.text or "").strip()

    uid: int | None = None

    # --- حالت آیدی عددی ---
    if re.fullmatch(r"\d{4,}", raw):
        uid = int(raw)

    # --- حالت یوزرنیم بدون فاصله/ایموجی ---
    elif re.fullmatch(r"@?[A-Za-z0-9_]{3,32}", raw):
        uname = raw.lstrip("@")
        try:
            chat = await message.bot.get_chat("@" + uname)
            uid = chat.id
        except Exception:
            return await message.reply(
                "❌ کاربری با این یوزرنیم یافت نشد.\n"
                "اگر مطمئن هستید درست است، به کاربر بگویید حتماً یک‌بار به ربات /start بزند."
            )

    else:
        # نه آیدی است، نه یوزرنیم → این پیام را ما نادیده می‌گیریم
        # تا هندلرهای دیگر (مثل دکمه‌های منو) آن را بگیرند.
        return

    # اگر به هر دلیل uid خالی ماند
    if uid is None:
        return

    mode = w["mode"]

    if mode == "add":
        ok = add_admin(uid)
        await message.reply("✅ ادمین اضافه شد." if ok else "ℹ️ این کاربر قبلاً ادمین بوده.")
    else:
        ok = remove_admin(uid)
        await message.reply("🗑 حذف شد." if ok else "⚠️ حذف ممکن نیست (در لیست ادمین‌ها نیست).")

    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)


# --------------------------------------------------------------------------- #
#                   مدیریت «کانال‌های من» — عضویت اجباری                     #
# --------------------------------------------------------------------------- #


@router.message(F.text == "📣 کانال‌های من")
async def admin_my_channels_root(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")

    # اگر قبلاً در حالت افزودن/حذف ادمین بود، آن را پاک کن (برای نظم بیشتر،
    # ولی دیگر تداخلی با منو نخواهد داشت چون هندلر بالا ورودی‌های منو را
    # نادیده می‌گیرد)
    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

    await message.answer(
        "مدیریت کانال‌های اجباری:",
        reply_markup=admin_my_channels_kb(),
    )


@router.message(F.text == "📋 لیست کانال‌های من")
async def list_my_channels_msg(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ اجازه ندارید.")

    items = list_required_channels()
    if not items:
        return await message.answer("هیچ کانالی ثبت نشده.")

    lines = ["📌 لیست کانال‌های اجباری:"]

    for ch in items:
        cid = int(ch["id"])
        stored_title = ch.get("title") or ""
        stored_username = ch.get("username") or ""

        # تلاش برای گرفتن اطلاعات واقعی از تلگرام
        try:
            info = await message.bot.get_chat(cid)
            real_title = getattr(info, "title", "") or getattr(info, "full_name", "")
            real_username = getattr(info, "username", "") or ""
        except Exception:
            real_title = stored_title
            real_username = stored_username

        title = real_title or stored_title or str(cid)
        username = real_username or stored_username

        txt = title
        if username:
            txt += f" • @{username}"
        if cid == SETTINGS.TARGET_GROUP_ID:
            txt += " • کانال اصلی"

        lines.append(txt)

    await message.answer("\n".join(lines))


@router.message(F.text == "➕ افزودن کانال من")
async def add_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")

    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "add"}
    await message.answer(
        "🔗 لینک کانال را ارسال کنید.\n"
        "مثال: https://t.me/testchannel\n"
        "فقط لینک‌های عمومی t.me/username قابل قبول هستند."
    )


@router.message(F.text == "🗑 حذف کانال من")
async def remove_my_channel_start(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ فقط مدیر اصلی اجازه دارد.")

    MEMBERS_CH_WAIT[message.from_user.id] = {"mode": "remove"}
    await message.answer(
        "🔗 لینک کانالی که باید حذف شود را ارسال کنید.\n"
        "مثال: https://t.me/testchannel"
    )


@router.message(F.text, F.from_user.id.func(lambda uid: uid in MEMBERS_CH_WAIT))
async def my_channels_flow(message: types.Message):
    st = MEMBERS_CH_WAIT.get(message.from_user.id)
    if not st:
        return

    ref = _extract_public_tme_username_from_link(message.text)
    if not ref:
        return await message.reply("❗ فقط لینک عمومی t.me/username مجاز است.")

    try:
        chat = await message.bot.get_chat(ref)
        cid = chat.id
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "")
        username = getattr(chat, "username", "") or ref.lstrip("@")
    except Exception:
        return await message.reply("❌ امکان دریافت اطلاعات کانال نیست.")

    if st["mode"] == "add":
        ok = add_required_channel(cid, title=title, username=username)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ این کانال از قبل ثبت شده است.")
    else:
        if cid == SETTINGS.TARGET_GROUP_ID:
            return await message.reply("⛔ حذف کانال اصلی مجاز نیست.")
        ok = remove_required_channel(cid)
        await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین کانالی در لیست وجود ندارد.")

    MEMBERS_CH_WAIT.pop(message.from_user.id, None)
