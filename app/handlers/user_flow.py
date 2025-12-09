from __future__ import annotations
import json
import re
from uuid import uuid4

from aiogram import Router, F, html, types, Bot
from aiogram.utils.media_group import MediaGroupBuilder

from ..config import SETTINGS
from ..keyboards import user_finish_kb, admin_review_kb
from ..storage import (
    next_daily_number,
    list_admins,
    is_admin,
    is_owner,
)
from .state import (
    MAX_PHOTOS,
    PENDING,
    PHOTO_WAIT,
)
from .membership import _user_is_member, build_join_kb
from .common import (
    contains_persian_digits,
    price_words,
    to_jalali,
)

router = Router()

# --------------------------------------------------------------------------- #
#                         توابع کمکی محلی                                     #
# --------------------------------------------------------------------------- #


def normalize_digits(s: str) -> str:
    """
    تبدیل ارقام فارسی/عربی به لاتین.
    فقط روی خود ارقام اثر می‌گذارد و بقیه کاراکترها را دست نمی‌زند.
    """
    if not s:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    trans_table = {ord(p): str(i) for i, p in enumerate(persian)}
    trans_table.update({ord(a): str(i) for i, a in enumerate(arabic)})
    return s.translate(trans_table)


# --------------------------------------------------------------------------- #
#                         کپشن اصلی (کانال مقصد)                             #
# --------------------------------------------------------------------------- #


def build_caption(
    form: dict,
    number: int,
    jdate: str,
    *,
    show_price: bool,
    show_desc: bool,
) -> str:
    ins_text = f"{form.get('insurance')} ماه" if form.get("insurance") else "—"
    phone = "\u200e09127475355\u200e"

    parts = [
        f"<b>{html.quote(form['category'])}</b>",
        f"<b>نام خودرو:</b> {html.quote(form['car'])}",
        f"<b>سال ساخت:</b> {html.quote(form['year'])}",
        f"<b>رنگ:</b> {html.quote(form['color'])}",
        f"<b>کارکرد:</b> {html.quote(form['km'])} کیلومتر",
        f"<b>مهلت بیمه:</b> {html.quote(ins_text)}",
        f"<b>گیربکس:</b> {html.quote(form.get('gear') or '—')}",
    ]

    if show_price and form.get("price_words"):
        parts.append(f"<b>قیمت:</b> {html.quote(form['price_words'])}")

    if show_desc and (form.get("desc") or "").strip():
        parts.append(f"<b>توضیحات:</b>\n{html.quote(form['desc'])}")

    parts.append("")
    parts.append(f"☎️ <b>تماس:</b>\nکیوان — {phone}")

    parts.append("───────────────────")

    # 🔖 شماره آگهی و تاریخ زیر هم
    parts.append(f"🔖 <b>آگهی شماره #{number}</b>")
    parts.append(f"📅 <i>{jdate}</i>")

    return "\n".join(parts)

# --------------------------------------------------------------------------- #
#                         کپشن مخصوص ادمین‌ها                                 #
# --------------------------------------------------------------------------- #


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

    lines: list[str] = []

    # اطلاعات تماس فقط برای owner
    if include_contact:
        lines.append(f"📞 {html.quote(phone or '—')}")
        uname = (username or "").lstrip("@")
        lines.append(f"👤 @{html.quote(uname)}" if uname else "👤 بدون نام کاربری")
        lines.append("")

    lines.append("🧪 <b>موارد نیازمند بررسی:</b>")
    lines.append(f"💵 قیمت: {html.quote(form.get('price_words') or '—')}")
    lines.append(f"📝 توضیحات:\n{html.quote(form.get('desc') or '—')}")
    lines.append("—" * 10)

    lines.append("📋 <b>خلاصه آگهی</b>")
    lines.append(f"نام خودرو: {html.quote(form['car'])}")
    lines.append(
        f"سال/رنگ/کارکرد: "
        f"{html.quote(form['year'])} / {html.quote(form['color'])} / {html.quote(form['km'])}km"
    )
    lines.append(
        f"بیمه/گیربکس: {html.quote(ins_text)} / {html.quote(form.get('gear') or '—')}"
    )

    lines.append(f"\n🗓️ <i>{jdate}</i> • ⏱ #{number}")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#                         اعتبارسنجی و نرمال‌سازی فرم                         #
# --------------------------------------------------------------------------- #


def validate_and_normalize(
    payload: dict,
) -> tuple[bool, str | None, dict | None]:
    cat = (payload.get("category") or "").strip()
    car = (payload.get("car") or "").strip()
    year = (payload.get("year") or "").strip()
    color = (payload.get("color") or "").strip()
    km = (payload.get("km") or "").strip()
    ins = (payload.get("insurance") or "").strip()
    gear = (payload.get("gear") or "").strip()
    desc = (payload.get("desc") or "").strip()
    phone = (payload.get("phone") or "").strip()

    # قیمت از WebApp (نام فیلد ممکن است price یا million_price باشد)
    price_raw = str(
        payload.get("million_price")
        or payload.get("price")
        or ""
    ).strip()

    # --- نرمال‌سازی ارقام (فارسی/عربی → لاتین) برای فیلدهای عددی --- #
    year = normalize_digits(year)
    km = normalize_digits(km)
    ins = normalize_digits(ins)
    phone = normalize_digits(phone)
    price_raw = normalize_digits(price_raw)
    # یکسان‌سازی ممیز اعشاری
    price_raw = (
        price_raw.replace(",", ".")
        .replace("\u066B", ".")  # Arabic decimal separator
        .replace("\u066C", ".")  # Arabic thousands separator (اگر استفاده شود)
    )

    # فقط در فیلدهایی که «کاملاً عددی» هستند، بعد از نرمال‌سازی، ارقام فارسی نباید بماند
    if (
        contains_persian_digits(year)
        or contains_persian_digits(km)
        or contains_persian_digits(ins)
        or contains_persian_digits(phone)
        or contains_persian_digits(price_raw)
    ):
        return False, "لطفاً فقط از اعداد لاتین (0-9) در اعداد استفاده کنید.", None

    # نام خودرو: فارسی + انگلیسی + عدد (فارسی/لاتین) + فاصله
    # محدود به ۲ تا ۴۰ کاراکتر، بدون سایر علائم
    if not re.fullmatch(
        r"[آ-یA-Za-z0-9\u06F0-\u06F9\u0660-\u0669\s]{2,40}", car
    ):
        return (
            False,
            "نام خودرو نامعتبر است (فقط حروف فارسی/انگلیسی، عدد و فاصله، بین ۲ تا ۴۰ کاراکتر).",
            None,
        )

    # سال ساخت: 4 رقم لاتین
    if not re.fullmatch(r"1[34]\d{2}", year):
        return False, "سال ساخت باید ۴ رقم لاتین باشد.", None

    # رنگ فارسی
    if not re.fullmatch(r"[آ-ی\s]{1,12}", color):
        return False, "رنگ باید حروف فارسی (حداکثر ۱۲ کاراکتر) باشد.", None

    # کارکرد
    if not re.fullmatch(r"\d{1,6}", km):
        return False, "کارکرد نامعتبر است.", None

    # بیمه
    if ins and not re.fullmatch(r"\d{1,2}", ins):
        return False, "مهلت بیمه باید بین 0 تا 99 ماه باشد.", None

    # شماره تماس
    if not re.fullmatch(r"09\d{9}", phone):
        return False, "شماره تماس باید با 09 شروع شده و ۱۱ رقم باشد.", None

    # ------------------------ قیمت بر اساس میلیون تومان ----------------------
    # مثل 80 ، 120.5 ، 1500.7
    if not re.fullmatch(r"\d+(\.\d{1,3})?", price_raw):
        return (
            False,
            "فرمت قیمت صحیح نیست. مثال: 120.5 (معادل 120 میلیون و 500 هزار).",
            None,
        )

    try:
        million_val = float(price_raw)
    except ValueError:
        return (
            False,
            "قیمت نامعتبر است. مثال: 80 یا 120.5",
            None,
        )

    toman = int(million_val * 1_000_000)  # تبدیل میلیون → تومان
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


# --------------------------------------------------------------------------- #
#                         دریافت فرم WebApp                                   #
# --------------------------------------------------------------------------- #


@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    # عضویت اجباری
    if not await _user_is_member(message.bot, message.from_user.id):
        await message.answer(
            "⛔ ابتدا در کانال‌های موردنیاز عضو شوید، سپس دوباره اقدام کنید.",
            reply_markup=await build_join_kb(message.bot),
        )
        return

    # داده‌ی WebApp
    try:
        data = json.loads(message.web_app_data.data or "{}")
    except Exception:
        data = {}

    ok, err, form = validate_and_normalize(data)
    if not ok:
        await message.answer(err or "اطلاعات نامعتبر است.")
        return

    form["username"] = message.from_user.username or ""

    token = uuid4().hex
    PENDING[token] = {
        "form": form,
        "user_id": message.from_user.id,
        "admin_msgs": [],
    }
    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": MAX_PHOTOS}

    await message.answer(
        "فرم شما ذخیره شد ✅\n"
        "اکنون تا ۵ عکس ارسال کنید. هر زمان آماده بودید، «📣 انتشار در گروه» را بزنید.",
        reply_markup=user_finish_kb(token),
    )


# --------------------------------------------------------------------------- #
#                         دریافت عکس‌ها                                       #
# --------------------------------------------------------------------------- #


@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess:
        return

    if "remain" not in sess or not isinstance(sess["remain"], int):
        sess["remain"] = MAX_PHOTOS

    if sess["remain"] <= 0:
        await message.reply(
            "حداکثر ۵ عکس مجاز است. سپس «📣 انتشار در گروه» را بزنید.",
            reply_markup=user_finish_kb(sess["token"]),
        )
        return

    file_id = message.photo[-1].file_id
    token = sess["token"]

    PENDING[token]["form"]["photos"].append(file_id)
    sess["remain"] -= 1
    left = max(sess["remain"], 0)

    await message.reply(
        f"عکس ثبت شد. باقی‌مانده: {left}",
        reply_markup=user_finish_kb(token),
    )


# --------------------------------------------------------------------------- #
#                         انتشار در کانال مقصد                                #
# --------------------------------------------------------------------------- #


async def publish_to_destination(
    bot: Bot,
    form: dict,
    *,
    show_price: bool,
    show_desc: bool,
):
    number, iso = next_daily_number()
    j = to_jalali(iso)

    caption = build_caption(
        form,
        number,
        j,
        show_price=show_price,
        show_desc=show_desc,
    )

    dest = SETTINGS.TARGET_GROUP_ID
    photos = form.get("photos") or []

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
            "jdate": j,
        }

    msg = await bot.send_message(dest, caption, parse_mode="HTML")
    return {
        "chat_id": msg.chat.id,
        "msg_id": msg.message_id,
        "has_photos": False,
        "number": number,
        "jdate": j,
    }


# --------------------------------------------------------------------------- #
#                         ارسال برای ادمین‌ها                                 #
# --------------------------------------------------------------------------- #


async def send_review_to_admins(
    bot: Bot,
    form: dict,
    token: str,
    photos: list[str],
    grp: dict,
) -> int:
    count = 0
    admins = list_admins()

    for admin_id in admins:
        try:
            include_contact = is_owner(admin_id)

            cap = admin_caption(
                form,
                grp["number"],
                grp["jdate"],
                phone=form.get("phone"),
                username=form.get("username"),
                include_contact=include_contact,
            )

            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=cap, parse_mode="HTML")
                for p in photos[1:MAX_PHOTOS]:
                    mg.add_photo(media=p)
                await bot.send_media_group(admin_id, mg.build())
            else:
                await bot.send_message(admin_id, cap, parse_mode="HTML")

            panel = await bot.send_message(
                admin_id,
                "📝 ویرایش/اعمال:\n"
                f"• قیمت فعلی: {html.quote(form.get('price_words') or '—')}\n"
                f"• توضیحات فعلی: {(html.quote(form.get('desc') or '—'))[:400]}\n",
                reply_markup=admin_review_kb(token),
                parse_mode="HTML",
            )

            PENDING[token]["admin_msgs"].append(
                (panel.chat.id, panel.message_id)
            )
            count += 1

        except Exception:
            pass

    return count


# --------------------------------------------------------------------------- #
#                         اتمام کاربر (دکمه انتشار)                           #
# --------------------------------------------------------------------------- #


@router.callback_query(F.data.startswith("finish:"))
async def cb_finish(call: types.CallbackQuery):
    token = call.data.split(":", 1)[1]

    data = PENDING.get(token)
    if not data or data["user_id"] != call.from_user.id:
        await call.answer("جلسه یافت نشد.", show_alert=True)
        return

    if not SETTINGS.TARGET_GROUP_ID:
        await call.answer("کانال مقصد در تنظیمات تعریف نشده.", show_alert=True)
        return

    form = data["form"]

    # انتشار در کانال اصلی (.env)
    grp = await publish_to_destination(
        call.bot,
        form,
        show_price=False,
        show_desc=False,
    )

    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": False, "desc": True}

    # ارسال برای ادمین‌ها
    photos = form.get("photos") or []
    await send_review_to_admins(call.bot, form, token, photos, grp)

    PHOTO_WAIT.pop(call.from_user.id, None)

    try:
        await call.message.edit_text("ثبت شد ✅ و برای بررسی به ادمین‌ها ارسال شد.")
    except Exception:
        pass

    await call.answer()
