from __future__ import annotations
from aiogram import Router, types, F

from ..config import SETTINGS
from ..keyboards import admin_review_kb
from ..storage import is_admin
from .state import PENDING, ADMIN_EDIT_WAIT
from .common import _parse_admin_price
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
        "قیمت جدید را با ارقام لاتین بفرستید (میلیون با اعشار یک‌رقمی یا تومان خالی)."
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
    await call.message.reply("توضیحات جدید را بفرستید.")
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

    if field == "price":
        ok, n_toman = _parse_admin_price(message.text)
        if not ok:
            await message.reply("عدد نامعتبر.")
            return
        form["price_num"] = n_toman
        form["price_words"] = price_words(n_toman)
        await message.reply(f"قیمت به «{form['price_words']}» تغییر کرد.")

    elif field == "desc":
        form["desc"] = message.text.strip()
        await message.reply("توضیحات به‌روزرسانی شد.")

    ADMIN_EDIT_WAIT.pop(message.from_user.id, None)

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
        # اگر ادیت نشد، پیام جدید ارسال می‌کنیم
        try:
            await call.bot.send_message(SETTINGS.TARGET_GROUP_ID, caption, parse_mode="HTML")
        except Exception:
            await call.answer("خطا در ارسال/ادیت پست.", show_alert=True)
            return

    # قفل کردن پنل ادمین‌ها
    for chat_id, msg_id in info["admin_msgs"]:
        try:
            await call.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
            await call.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="✅ اعمال شد روی پست گروه")
        except Exception:
            pass

    await call.answer("اعمال شد.")
    try:
        await call.message.edit_text("✅ اعمال شد روی پست گروه")
    except Exception:
        pass

    PENDING.pop(token, None)

# --------------------------------------------------------------------------- #
#                              رد کردن / حذف پست                              #
# --------------------------------------------------------------------------- #

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    """
    وقتی ادمین آگهی را رد می‌کند:
      - اگر تصویر دارد → حذف کامل مدیاگروپ
      - اگر متن است → حذف تک پیام
      - پیام‌های ادمین قفل می‌شوند
      - از PENDING حذف می‌شود
    """

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

    # حذف پیام اصلی
    if chat_id and msg_id:
        try:
            await call.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
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
        except Exception:
            pass

    # حذف از حافظه
    PENDING.pop(token, None)

    await call.answer("آگهی حذف شد.", show_alert=True)

    try:
        await call.message.edit_text("❌ آگهی حذف شد.")
    except Exception:
        pass
