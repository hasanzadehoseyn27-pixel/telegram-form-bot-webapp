from __future__ import annotations
from aiogram import Router, types, F

import re  # ← لازم برای regex جدید

from ..config import SETTINGS
from ..keyboards import admin_review_kb
from ..storage import is_admin
from .state import PENDING, ADMIN_EDIT_WAIT
from .common import normalize_digits  # ← برای تبدیل ارقام فارسی
from .user_flow import build_caption, price_words

router = Router()

# --------------------------------------------------------------------------- #
#                        ویرایش قیمت / توضیحات توسط ادمین                    #
# --------------------------------------------------------------------------- #

@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return

    token = call.data.split(":", 1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True)
        return

    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}

    await call.message.reply(
        "📝 قیمت جدید را وارد کنید.\n"
        "مثال: 80 (میلیون) یا 120.5 یا 2500\n"
        "همه به میلیون تومان محاسبه می‌شوند."
    )
    await call.answer()


@router.callback_query(F.data.startswith("edit_desc:"))
async def cb_edit_desc(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return

    token = call.data.split(":", 1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True)
        return

    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "desc"}

    await call.message.reply("📝 متن جدید توضیحات را ارسال کنید.")
    await call.answer()


@router.message(F.text, F.from_user.id.func(lambda uid: uid in ADMIN_EDIT_WAIT))
async def on_admin_text_edit(message: types.Message):
    w = ADMIN_EDIT_WAIT.get(message.from_user.id)
    if not w or not is_admin(message.from_user.id):
        return

    token, field = w["token"], w["field"]
    info = PENDING.get(token)

    if not info:
        ADMIN_EDIT_WAIT.pop(message.from_user.id, None)
        await message.reply("درخواست یافت نشد.")
        return

    form = info["form"]

    # ------------------- ویرایش قیمت -------------------
    if field == "price":

        # 1) تبدیل ارقام فارسی → لاتین
        raw = normalize_digits(message.text or "").replace(",", ".").strip()

        # 2) همان regex فرم اولیه
        if not re.fullmatch(r"\d+(\.\d{1,3})?", raw):
            await message.reply("❌ قیمت نامعتبر است.\nمثال: 80 یا 120.5 یا 2500")
            return

        # 3) تبدیل به float
        try:
            million = float(raw)
        except:
            await message.reply("❌ فرمت عددی صحیح نیست.")
            return

        # 4) تبدیل به تومان
        n_toman = int(round(million * 1_000_000))

        # 5) ساخت price_words مثل فرم
        form["price_num"] = n_toman
        form["price_words"] = price_words(n_toman)

        await message.reply(f"💰 قیمت جدید ثبت شد: «{form['price_words']}»")

    # ------------------- ویرایش توضیحات -------------------
    elif field == "desc":
        form["desc"] = message.text.strip()
        await message.reply("📝 توضیحات به‌روزرسانی شد.")

    # پاک‌کردن وضعیت انتظار
    ADMIN_EDIT_WAIT.pop(message.from_user.id, None)

    # نمایش پنل دوباره
    await message.answer(
        "ویرایش/اعمال:\n"
        f"• قیمت فعلی: {form.get('price_words') or '—'}\n"
        f"• توضیحات فعلی: {(form.get('desc') or '—')[:400]}\n\n"
        "یک مورد را انتخاب کنید:",
        reply_markup=admin_review_kb(token),
    )


# --------------------------------------------------------------------------- #
#                            اعمال نهایی روی پست                              #
# --------------------------------------------------------------------------- #

@router.message(F.text.startswith("/show"))
async def show_hidden(message: types.Message):
    raw = message.text.split(" ",1)[1]
    await message.answer( ''.join(f"{ord(c)} " for c in raw) )


@router.callback_query(F.data.startswith("publish:"))
async def cb_publish(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return

    token = call.data.split(":", 1)[1]
    info = PENDING.get(token)

    if not info:
        await call.answer("درخواست یافت نشد.", show_alert=True)
        return

    form = info["form"]
    grp  = info["grp"]
    needs = info["needs"]

    show_price = not needs.get("price") or bool(form.get("price_words"))
    show_desc  = not needs.get("desc")  or bool(form.get("desc"))

    caption = build_caption(
        form,
        grp["number"],
        grp["jdate"],
        show_price=show_price,
        show_desc=show_desc
    )

    # اعمال و ویرایش پست اصلی
    try:
        if grp["has_photos"]:
            await call.bot.edit_message_caption(
                chat_id=grp["chat_id"],
                message_id=grp["msg_id"],
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await call.bot.edit_message_text(
                chat_id=grp["chat_id"],
                message_id=grp["msg_id"],
                text=caption,
                parse_mode="HTML",
            )
    except Exception:
        try:
            # ✅ فالبک باید به همان مقصد واقعی برود (نه SETTINGS ثابت)
            await call.bot.send_message(grp["chat_id"], caption, parse_mode="HTML")
        except Exception:
            await call.answer("خطا در ارسال/ادیت پست.", show_alert=True)
            return

    # بستن صفحهٔ ادمین‌ها
    for admin_chat_id, admin_msg_id in info["admin_msgs"]:
        try:
            await call.bot.edit_message_reply_markup(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                reply_markup=None
            )
            await call.bot.edit_message_text(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                text="✅ تغییرات روی پست اعمال شد"
            )
        except Exception:
            pass

    await call.answer("اعمال شد.")

    # پیام خود ادمین
    try:
        await call.message.edit_text("✅ تغییرات روی پست اعمال شد")
    except Exception:
        pass

    # حذف از حالت pending
    PENDING.pop(token, None)


# --------------------------------------------------------------------------- #
#                              رد کردن / حذف پست                              #
# --------------------------------------------------------------------------- #

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return

    token = call.data.split(":", 1)[1]
    info = PENDING.get(token)

    if not info:
        await call.answer("درخواست یافت نشد.", show_alert=True)
        return

    grp = info.get("grp", {})
    chat_id = grp.get("chat_id")
    msg_id = grp.get("msg_id")

    # حذف پست اصلی
    if chat_id and msg_id:
        try:
            await call.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass

    # قفل کردن پیام‌های ادمین
    for admin_chat_id, admin_msg_id in info.get("admin_msgs", []):
        try:
            await call.bot.edit_message_reply_markup(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                reply_markup=None
            )
            await call.bot.edit_message_text(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                text="❌ این آگهی توسط ادمین رد شد."
            )
        except:
            pass

    # حذف از حافظه
    PENDING.pop(token, None)

    await call.answer("آگهی حذف شد.", show_alert=True)

    try:
        await call.message.edit_text("❌ آگهی حذف شد.")
    except:
        pass
