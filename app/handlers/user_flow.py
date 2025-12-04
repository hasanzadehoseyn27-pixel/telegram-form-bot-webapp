from __future__ import annotations
import json, re
from uuid import uuid4

from aiogram import Router, F, html, types, Bot
from aiogram.utils.media_group import MediaGroupBuilder

from ..config import SETTINGS
from ..keyboards import user_finish_kb, admin_review_kb
from ..storage import (
    next_daily_number,
    list_admins, is_admin, is_owner,
)
from .state import (
    MAX_PHOTOS, PENDING, PHOTO_WAIT,
)
from .membership import _user_is_member, build_join_kb
from .common import (
    contains_persian_digits,
    price_words,
    to_jalali,
)

router = Router()


# ------------------------ کپشن اصلی ------------------------

def build_caption(form: dict, number: int, jdate: str, *, show_price: bool, show_desc: bool) -> str:
    ins_text = f"{form.get('insurance')} ماه" if form.get("insurance") else "—"
    lrm_number = "\u200e09127475355\u200e"

    parts = [
        f"⏱️ <b>شماره آگهی: #{number}</b>",
        f"🏷️ <b>نام خودرو:</b> {html.quote(form['car'])}",
        f"📅 <b>سال ساخت:</b> {html.quote(form['year'])}",
        f"🎨 <b>رنگ:</b> {html.quote(form['color'])}",
        f"📈 <b>کارکرد:</b> {html.quote(form['km'])} کیلومتر",
        f"🛡️ <b>مهلت بیمه (ماه):</b> {html.quote(ins_text)}",
        f"⚙️ <b>گیربکس:</b> {html.quote(form.get('gear') or '—')}",
    ]

    if show_price and form.get("price_words"):
        parts.append(f"💵 <b>قیمت:</b> {html.quote(form['price_words'])}")

    if show_desc and form.get("desc"):
        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")

    parts.append(f"☎️ <b>تماس:</b>\nکیوان — {lrm_number}")
    parts.append(f"\n🗓️ <i>{jdate}</i>")
    return "\n".join(parts)



# ------------------------ کپشن مخصوص ادمین ------------------------

def admin_caption(
    form: dict,
    number: int,
    jdate: str,
    *,
    phone: str | None = None,
    username: str | None = None,
    include_contact: bool = False,
) -> str:

    ins_text = f"{form.get('insurance')} ماه" if form.get("insurance") else "—"

    lines = []

    if include_contact:
        lines.append(f"📞 {phone or '—'}")
        uname = (username or "").lstrip("@")
        lines.append(f"👤 @{uname}" if uname else "👤 بدون نام کاربری")
        lines.append("")

    lines.append("🧪 <b>موارد نیازمند بررسی:</b>")
    lines.append(f"💵 قیمت: {form.get('price_words') or '—'}")
    lines.append(f"📝 توضیحات:\n{form.get('desc') or '—'}")
    lines.append("—" * 10)

    lines.append("📋 <b>خلاصه آگهی</b>")
    lines.append(f"نام خودرو: {form['car']}")
    lines.append(f"سال/رنگ/کارکرد: {form['year']} / {form['color']} / {form['km']}km")
    lines.append(f"بیمه/گیربکس: {ins_text} / {form.get('gear') or '—'}")

    lines.append(f"\n🗓️ <i>{jdate}</i> • ⏱ # {number}")

    return "\n".join(lines)



# ------------------------ اعتبارسنجی ورودی ------------------------

def validate_and_normalize(payload: dict):
    cat = payload.get("category", "").strip()
    car = payload.get("car", "").strip()
    year = payload.get("year", "").strip()
    color = payload.get("color", "").strip()
    km = payload.get("km", "").strip()
    ins = payload.get("insurance", "").strip()
    gear = payload.get("gear", "").strip()
    desc = payload.get("desc", "").strip()
    phone = payload.get("phone", "").strip()
    million_price = str(payload.get("million_price", "")).strip()

    # جلوگیری از ارقام فارسی
    if (
        contains_persian_digits(car)
        or contains_persian_digits(year)
        or contains_persian_digits(km)
        or contains_persian_digits(ins)
        or contains_persian_digits(phone)
        or contains_persian_digits(million_price)
    ):
        return False, "لطفاً فقط از اعداد لاتین استفاده کنید.", None

    # نام خودرو فارسی یا انگلیسی یا عدد
    if not re.fullmatch(r"[آ-یA-Za-z0-9\s]{2,40}", car):
        return False, "نام خودرو نامعتبر است (فقط فارسی/انگلیسی/عدد).", None

    if not re.fullmatch(r"\d{4}", year):
        return False, "سال ساخت باید ۴ رقم باشد.", None

    if not re.fullmatch(r"[آ-ی\s]{1,12}", color):
        return False, "رنگ باید فارسی باشد.", None

    if not re.fullmatch(r"\d{1,6}", km):
        return False, "کارکرد نامعتبر است.", None

    if ins and not re.fullmatch(r"\d{1,2}", ins):
        return False, "مهلت بیمه 0 تا 99 ماه.", None

    if not re.fullmatch(r"09\d{9}", phone):
        return False, "شماره تماس صحیح نیست.", None

    # ------------------------ قیمت میلیون + اعشار ------------------------

    if not re.fullmatch(r"\d+(\.\d{1,3})?", million_price):
        return False, "فرمت قیمت صحیح نیست (مثال: 120.5 یا 1500.7).", None

    million_val = float(million_price)
    toman = int(million_val * 1_000_000)   # تبدیل میلیون → تومان
    price_text = price_words(toman)

    form = {
        "category": cat,
        "car": car,
        "year": year,
        "color": color,
        "km": km,
        "insurance": ins,
        "gear": gear,
        "desc": desc,
        "phone": phone,
        "username": "",
        "photos": [],
        "price_num": toman,
        "price_words": price_text,
    }

    return True, None, form



# ------------------------ دریافت فرم WebApp ------------------------

@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):

    if not await _user_is_member(message.bot, message.from_user.id):
        await message.answer(
            "⛔ ابتدا در کانال‌های موردنیاز عضو شوید.",
            reply_markup=await build_join_kb(message.bot),
        )
        return

    try:
        data = json.loads(message.web_app_data.data or "{}")
    except:
        data = {}

    ok, err, form = validate_and_normalize(data)
    if not ok:
        return await message.answer(err or "اطلاعات نامعتبر است.")

    form["username"] = message.from_user.username or ""

    token = uuid4().hex
    PENDING[token] = {
        "form": form,
        "user_id": message.from_user.id,
        "admin_msgs": [],
    }

    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": MAX_PHOTOS}

    await message.answer(
        "فرم ذخیره شد. اکنون تا ۵ عکس ارسال کنید.",
        reply_markup=user_finish_kb(token),
    )



# ------------------------ دریافت عکس‌ها ------------------------

@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess:
        return

    if sess["remain"] <= 0:
        await message.answer(
            "حداکثر ۵ عکس. برای انتشار آماده‌اید.",
            reply_markup=user_finish_kb(sess["token"]),
        )
        return

    file_id = message.photo[-1].file_id
    token = sess["token"]

    PENDING[token]["form"]["photos"].append(file_id)

    sess["remain"] -= 1
    left = sess["remain"]

    await message.reply(
        f"عکس ثبت شد. باقی‌مانده: {left}",
        reply_markup=user_finish_kb(token),
    )



# ------------------------ انتشار پست ------------------------

async def publish_to_destination(bot: Bot, form: dict, *, show_price: bool, show_desc: bool):

    number, iso = next_daily_number()
    j = to_jalali(iso)
    caption = build_caption(
        form, number, j,
        show_price=show_price,
        show_desc=show_desc
    )

    dest = SETTINGS.TARGET_GROUP_ID
    photos = form["photos"]

    if photos:
        mg = MediaGroupBuilder()
        mg.add_photo(media=photos[0], caption=caption, parse_mode="HTML")
        for p in photos[1:MAX_PHOTOS]:
            mg.add_photo(media=p)

        msgs = await bot.send_media_group(dest, mg.build())
        first = msgs[0]

        return {
            "chat_id": first.chat.id,
            "msg_id": first.message_id,
            "has_photos": True,
            "number": number,
            "jdate": j
        }

    else:
        msg = await bot.send_message(dest, caption, parse_mode="HTML")
        return {
            "chat_id": msg.chat.id,
            "msg_id": msg.message_id,
            "has_photos": False,
            "number": number,
            "jdate": j
        }



# ------------------------ ارسال برای ادمین‌ها ------------------------

async def send_review_to_admins(bot, form, token, photos, grp):
    count = 0
    admins = list_admins()

    for admin_id in admins:
        try:
            include_contact = is_owner(admin_id)

            cap = admin_caption(
                form,
                grp["number"],
                grp["jdate"],
                phone=form["phone"],
                username=form["username"],
                include_contact=include_contact,
            )

            # ارسال تصاویر
            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=cap, parse_mode="HTML")
                for p in photos[1:MAX_PHOTOS]:
                    mg.add_photo(media=p)
                await bot.send_media_group(admin_id, mg.build())
            else:
                await bot.send_message(admin_id, cap, parse_mode="HTML")

            # پنل اکشن
            panel = await bot.send_message(
                admin_id,
                f"📝 ویرایش/اعمال:\n"
                f"• قیمت فعلی: {form['price_words']}\n"
                f"• توضیحات فعلی: {(form['desc'] or '—')[:400]}\n",
                reply_markup=admin_review_kb(token),
                parse_mode="HTML",
            )

            PENDING[token]["admin_msgs"].append((panel.chat.id, panel.message_id))
            count += 1

        except:
            pass

    return count



# ------------------------ پایان کاربر ------------------------

@router.callback_query(F.data.startswith("finish:"))
async def cb_finish(call: types.CallbackQuery):
    token = call.data.split(":", 1)[1]

    data = PENDING.get(token)
    if not data or data["user_id"] != call.from_user.id:
        return await call.answer("جلسه یافت نشد.", show_alert=True)

    if not SETTINGS.TARGET_GROUP_ID:
        return await call.answer("کانال مقصد در تنظیمات تعریف نشده.", show_alert=True)

    form = data["form"]

    # انتشار اولیه
    grp = await publish_to_destination(
        call.bot,
        form,
        show_price=True,
        show_desc=False
    )

    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": False, "desc": True}

    # ارسال برای ادمین‌ها
    photos = form["photos"]
    await send_review_to_admins(call.bot, form, token, photos, grp)

    PHOTO_WAIT.pop(call.from_user.id, None)

    try:
        await call.message.edit_text("ثبت شد و برای بررسی ادمین ارسال شد.")
    except:
        pass

    await call.answer()
