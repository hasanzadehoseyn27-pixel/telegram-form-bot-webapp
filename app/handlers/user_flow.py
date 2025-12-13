from __future__ import annotations
import json
import re
import base64
import io
from uuid import uuid4

from aiogram import Router, F, html, types, Bot
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import BufferedInputFile

from ..config import SETTINGS
from ..keyboards import admin_review_kb
from ..storage import (
    next_daily_number,
    list_admins,
)
from .state import (
    MAX_PHOTOS,
    PENDING,
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
    phone = "\u200e09121513089\u200e"
    contact_name = "حاجی اسماعیلی"

    # ✅ راست‌چین کردن سال
    year_rtl = f"\u200f{form['year']}\u200f"

    parts = [
        f"🏷 {form['category']}",
        form['car'],
        year_rtl,
        form['color'],
    ]

    # ✅ قیمت زیر رنگ
    if show_price and form.get("price_words"):
        parts.append(f"قیمت: {form['price_words']}")

    # بقیه اطلاعات
    parts.append(f"کارکرد: {form['km']} کیلومتر")
    parts.append(f"مهلت بیمه: {ins_text}")
    parts.append(f"گیربکس: {form.get('gear') or '—'}")

    # ✅ توضیحات
    if show_desc and (form.get("desc") or "").strip():
        parts.append(f"\n{form['desc']}")

    parts.append("")
    parts.append(f"☎️ تماس:")
    parts.append(f"{contact_name} - {phone}")
    
    parts.append("───────────────────")
    
    parts.append(f"🔖 آگهی شماره #{number}")
    parts.append(f"📅 {jdate}")

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

    # اطلاعات تماس برای همه ادمین‌ها
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

    # قیمت از WebApp
    price_raw = str(
        payload.get("million_price")
        or payload.get("price")
        or ""
    ).strip()

    # --- نرمال‌سازی ارقام (فارسی/عربی → لاتین) ---
    year = normalize_digits(year)
    km = normalize_digits(km)
    ins = normalize_digits(ins)
    phone = normalize_digits(phone)
    price_raw = normalize_digits(price_raw)
    
    # یکسان‌سازی ممیز اعشاری
    price_raw = (
        price_raw.replace(",", ".")
        .replace("\u066B", ".")
        .replace("\u066C", ".")
    )

    # بررسی باقی‌مانده ارقام فارسی
    if (
        contains_persian_digits(year)
        or contains_persian_digits(km)
        or contains_persian_digits(ins)
        or contains_persian_digits(phone)
        or contains_persian_digits(price_raw)
    ):
        return False, "لطفاً فقط از اعداد لاتین (0-9) استفاده کنید.", None

    # نام خودرو
    if not re.fullmatch(
        r"[آ-یA-Za-z0-9\u06F0-\u06F9\u0660-\u0669\s]{2,40}", car
    ):
        return (
            False,
            "نام خودرو نامعتبر است.",
            None,
        )

    # سال ساخت: 4 رقم (شمسی 13xx-14xx یا میلادی 20xx)
    if not re.fullmatch(r"(1[34]\d{2}|20[012]\d)", year):
        return False, "سال ساخت باید ۴ رقم باشد (مثلاً ۱۴۰۱ یا 2018).", None

    # رنگ فارسی
    if not re.fullmatch(r"[آ-ی\s]{1,12}", color):
        return False, "رنگ باید حروف فارسی باشد.", None

    # کارکرد
    if not re.fullmatch(r"\d{1,6}", km):
        return False, "کارکرد نامعتبر است.", None

    # بیمه
    if ins and not re.fullmatch(r"\d{1,2}", ins):
        return False, "مهلت بیمه نامعتبر است.", None

    # شماره تماس
    if not re.fullmatch(r"09\d{9}", phone):
        return False, "شماره تماس باید با 09 شروع شده و ۱۱ رقم باشد.", None

    # قیمت
    if not re.fullmatch(r"\d+(\.\d{1,3})?", price_raw):
        return (
            False,
            "فرمت قیمت صحیح نیست.",
            None,
        )

    try:
        million_val = float(price_raw)
    except ValueError:
        return (
            False,
            "قیمت نامعتبر است.",
            None,
        )

    toman = int(million_val * 1_000_000)
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
            cap = admin_caption(
                form,
                grp["number"],
                grp["jdate"],
                phone=form.get("phone"),
                username=form.get("username"),
                include_contact=True,  # ✅ همه ادمین‌ها می‌بینن
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

    # ✅ پردازش عکس‌های base64
    photos_base64 = data.get("photos", [])
    photo_file_ids = []

    if photos_base64:
        await message.answer("⏳ در حال پردازش عکس‌ها...")

        for idx, base64_str in enumerate(photos_base64[:MAX_PHOTOS]):
            try:
                # حذف header داده base64
                if "," in base64_str:
                    base64_str = base64_str.split(",", 1)[1]

                # تبدیل base64 به bytes
                image_bytes = base64.b64decode(base64_str)

                # آپلود به تلگرام
                photo_file = BufferedInputFile(image_bytes, filename=f"photo_{idx+1}.jpg")
                sent_msg = await message.answer_photo(photo_file)

                # ذخیره file_id و حذف پیام
                photo_file_ids.append(sent_msg.photo[-1].file_id)
                await sent_msg.delete()

            except Exception as e:
                print(f"❌ خطا در پردازش عکس {idx+1}: {e}")
                continue

    form["photos"] = photo_file_ids

    # ✅ انتشار مستقیم (بدون دکمه انتشار)
    if not SETTINGS.TARGET_GROUP_ID:
        await message.answer("❌ کانال مقصد در تنظیمات تعریف نشده.")
        return

    token = uuid4().hex

    # انتشار در کانال اصلی
    grp = await publish_to_destination(
        message.bot,
        form,
        show_price=False,
        show_desc=False,
    )

    PENDING[token] = {
        "form": form,
        "user_id": message.from_user.id,
        "admin_msgs": [],
        "grp": grp,
        "needs": {"price": False, "desc": True}
    }

    # ارسال برای ادمین‌ها
    await send_review_to_admins(message.bot, form, token, photo_file_ids, grp)

    await message.answer(
        "✅ آگهی شما ثبت و منتشر شد!\n"
        "در حال بررسی توسط ادمین‌ها..."
    )
