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
    get_active_destination,
    get_active_id_and_title,
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
    """
    if not s:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    trans_table = {ord(p): str(i) for i, p in enumerate(persian)}
    trans_table.update({ord(a): str(i) for i, a in enumerate(arabic)})
    return s.translate(trans_table)


def to_persian_digits(s: str) -> str:
    """
    تبدیل اعداد لاتین به فارسی.
    """
    if not s:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(persian[int(c)] if c.isdigit() else c for c in s)


def to_persian_year(year_str: str) -> str:
    """
    تبدیل سال به فارسی.
    """
    return to_persian_digits(year_str)


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
    
    # نام و شماره تماس (دستی)
    # contact_1_name = "حاجی اسماعیلی"
    # contact_1_phone = "09121513089"
    contact_2_name = "کیوان"
    contact_2_phone = "09127475355"
    
    # سال: فقط به فارسی تبدیل
    year_display = to_persian_year(form['year'])
    
    parts = [
        f"🏷 <b>{html.quote(form['category'])}</b>",
        f"{html.quote(form['car'])}",
        f"\u200F{year_display}\u200F",  # راست‌چین
        f"{html.quote(form['color'])}",
    ]
    
    # قیمت زیر رنگ
    if show_price and form.get("price_words"):
        parts.append(f"قیمت: {html.quote(form['price_words'])}")
    
    parts.extend([
        f"کارکرد: {html.quote(form['km'])} کیلومتر",
        f"مهلت بیمه: {html.quote(ins_text)}",
        f"گیربکس: {html.quote(form.get('gear') or '—')}",
    ])
    
    # توضیحات
    if show_desc and (form.get("desc") or "").strip():
        parts.append("")
        parts.append(f"<b>توضیحات:</b>")
        parts.append(f"{html.quote(form['desc'])}")
    
    parts.append("")
    parts.append(f"☎️ <b>تماس:</b>")
    # parts.append(f"{contact_1_name} - \u200e{contact_1_phone}\u200e")
    parts.append(f"{contact_2_name} - \u200e{contact_2_phone}\u200e")
    
    parts.append("───────────────────")
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
) -> str:
    """
    همه ادمین‌ها شماره و یوزرنیم رو می‌بینن
    """
    ins_text = f"{form.get('insurance')} ماه" if form.get("insurance") else "—"
    
    lines: list[str] = []
    
    # اطلاعات تماس برای همه ادمین‌ها
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
    
    price_raw = str(
        payload.get("million_price")
        or payload.get("price")
        or ""
    ).strip()
    
    # نرمال‌سازی ارقام
    year = normalize_digits(year)
    km = normalize_digits(km)
    ins = normalize_digits(ins)
    phone = normalize_digits(phone)
    price_raw = normalize_digits(price_raw)
    price_raw = price_raw.replace(",", ".").replace("\u066B", ".").replace("\u066C", ".")
    
    # چک کردن ارقام فارسی باقیمانده
    if (
        contains_persian_digits(year)
        or contains_persian_digits(km)
        or contains_persian_digits(ins)
        or contains_persian_digits(phone)
        or contains_persian_digits(price_raw)
    ):
        return False, "لطفاً فقط از اعداد لاتین استفاده کنید.", None
    
    # نام خودرو
    if not re.fullmatch(r"[آ-یA-Za-z0-9\u06F0-\u06F9\u0660-\u0669\s]{2,40}", car):
        return False, "نام خودرو نامعتبر است.", None
    
    # سال: شمسی (1300-1430) یا میلادی (2000-2029)
    if not re.fullmatch(r"(1[34]\d{2}|20[012]\d)", year):
        return False, "سال ساخت باید ۴ رقم باشد (مثلاً 1403 یا 2024).", None
    
    # رنگ
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
        return False, "شماره تماس باید ۱۱ رقم باشد.", None
    
    # قیمت
    if not re.fullmatch(r"\d+(\.\d{1,3})?", price_raw):
        return False, "فرمت قیمت صحیح نیست.", None
    
    try:
        million_val = float(price_raw)
    except ValueError:
        return False, "قیمت نامعتبر است.", None
    
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
#                         دریافت فرم WebApp                                   #
# --------------------------------------------------------------------------- #

@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    if not await _user_is_member(message.bot, message.from_user.id):
        await message.answer(
            "⛔ ابتدا در کانال‌های موردنیاز عضو شوید، سپس دوباره اقدام کنید.",
            reply_markup=await build_join_kb(message.bot),
        )
        return
    
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
        "اکنون می‌توانید تا 3 عکس ارسال کنید، در غیر اینصورت \"تایید نهایی\" را بزنید تا آگهی شما در کانال منتشر شود.",
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
            "حداکثر ۵ عکس مجاز است. سپس «✅ تایید نهایی» را بزنید.",
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

    # ✅ مقصد فعال از storage (نه TARGET_GROUP_ID ثابت)
    dest = int(get_active_destination() or 0)
    if not dest:
        dest = int(SETTINGS.TARGET_GROUP_ID or 0)

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
            # همه ادمین‌ها شماره و یوزرنیم رو می‌بینن
            cap = admin_caption(
                form,
                grp["number"],
                grp["jdate"],
                phone=form.get("phone"),
                username=form.get("username"),
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
#                         اتمام کاربر (دکمه تایید نهایی)                      #
# --------------------------------------------------------------------------- #

@router.callback_query(F.data.startswith("finish:"))
async def cb_finish(call: types.CallbackQuery):
    token = call.data.split(":", 1)[1]
    
    data = PENDING.get(token)
    if not data or data["user_id"] != call.from_user.id:
        await call.answer("جلسه یافت نشد.", show_alert=True)
        return
    
    # مقصد فعال را می‌گیریم
    dest = int(get_active_destination() or 0)
    if not dest:
        dest = int(SETTINGS.TARGET_GROUP_ID or 0)

    if not dest:
        await call.answer("کانال مقصد در تنظیمات تعریف نشده.", show_alert=True)
        return
    
    form = data["form"]
    
    # انتشار در کانال
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


# --------------------------------------------------------------------------- #
#                  دکمه‌های ادمین: ویرایش قیمت و توضیحات                      #
# --------------------------------------------------------------------------- #

@router.callback_query(F.data.startswith("admin_edit_price:"))
async def cb_admin_edit_price(call: types.CallbackQuery):
    """ویرایش قیمت توسط ادمین"""
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return
    
    token = call.data.split(":", 1)[1]
    data = PENDING.get(token)
    
    if not data:
        await call.answer("❌ درخواست یافت نشد یا منقضی شده است.", show_alert=True)
        return
    
    await call.answer("لطفاً قیمت جدید را بر اساس میلیون تومان ارسال کنید.\nمثال: 120.5")
    # اینجا باید state یا handler برای دریافت پیام بعدی ادمین اضافه کنید


@router.callback_query(F.data.startswith("admin_edit_desc:"))
async def cb_admin_edit_desc(call: types.CallbackQuery):
    """ویرایش توضیحات توسط ادمین"""
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return
    
    token = call.data.split(":", 1)[1]
    data = PENDING.get(token)
    
    if not data:
        await call.answer("❌ درخواست یافت نشد یا منقضی شده است.", show_alert=True)
        return
    
    await call.answer("لطفاً توضیحات جدید را ارسال کنید.")
    # اینجا باید state یا handler برای دریافت پیام بعدی ادمین اضافه کنید


@router.callback_query(F.data.startswith("admin_apply_price:"))
async def cb_admin_apply_price(call: types.CallbackQuery):
    """اعمال قیمت در کانال"""
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return
    
    token = call.data.split(":", 1)[1]
    data = PENDING.get(token)
    
    if not data:
        await call.answer("❌ درخواست یافت نشد یا منقضی شده است.", show_alert=True)
        return
    
    grp = data.get("grp")
    if not grp:
        await call.answer("اطلاعات پیام کانال یافت نشد.", show_alert=True)
        return
    
    form = data["form"]
    
    # بروزرسانی کپشن با قیمت
    new_caption = build_caption(
        form,
        grp["number"],
        grp["jdate"],
        show_price=True,
        show_desc=data["needs"].get("desc", False),
    )
    
    try:
        await call.bot.edit_message_caption(
            chat_id=grp["chat_id"],
            message_id=grp["msg_id"],
            caption=new_caption,
            parse_mode="HTML",
        )
        data["needs"]["price"] = True
        await call.answer("✅ قیمت اعمال شد.", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ خطا: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_apply_desc:"))
async def cb_admin_apply_desc(call: types.CallbackQuery):
    """اعمال توضیحات در کانال"""
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True)
        return
    
    token = call.data.split(":", 1)[1]
    data = PENDING.get(token)
    
    if not data:
        await call.answer("❌ درخواست یافت نشد یا منقضی شده است.", show_alert=True)
        return
    
    grp = data.get("grp")
    if not grp:
        await call.answer("اطلاعات پیام کانال یافت نشد.", show_alert=True)
        return
    
    form = data["form"]
    
    # بروزرسانی کپشن با توضیحات
    new_caption = build_caption(
        form,
        grp["number"],
        grp["jdate"],
        show_price=data["needs"].get("price", False),
        show_desc=True,
    )
    
    try:
        await call.bot.edit_message_caption(
            chat_id=grp["chat_id"],
            message_id=grp["msg_id"],
            caption=new_caption,
            parse_mode="HTML",
        )
        data["needs"]["desc"] = True
        await call.answer("✅ توضیحات اعمال شد.", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ خطا: {e}", show_alert=True)
