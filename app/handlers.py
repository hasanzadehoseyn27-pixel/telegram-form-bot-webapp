import json, re
from uuid import uuid4
from datetime import datetime
import jdatetime

from aiogram import Router, F, html, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.media_group import MediaGroupBuilder

from .config import SETTINGS
from .keyboards import start_keyboard, admin_review_kb
from .storage import next_daily_number

router = Router()

# حافظه‌های موقت
PENDING: dict[str, dict] = {}          # token -> فرم و عکس‌ها تا انتشار
PHOTO_WAIT: dict[int, dict] = {}       # user_id -> {token, remain}
ADMIN_EDIT_WAIT: dict[int, dict] = {}  # admin_id -> {token, field}
EXTRA_ADMINS: set[int] = set()         # ادمین‌های runtime

def is_admin(uid: int) -> bool:
    return uid in SETTINGS.ADMIN_IDS or uid in EXTRA_ADMINS

def to_jalali(date_iso: str) -> str:
    y, m, d = map(int, date_iso.split("-"))
    g = datetime(y, m, d)
    j = jdatetime.date.fromgregorian(date=g)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"

def fmt_price_to_words(num: int) -> str:
    # خیلی ساده: هزار/میلیون/میلیارد
    if num >= 1_000_000_000:
        v = num // 1_000_000_000
        return f"{v} میلیارد تومان"
    if num >= 1_000_000:
        v = num // 1_000_000
        return f"{v} میلیون تومان"
    if num >= 1_000:
        v = num // 1_000
        return f"{v*1000:,} تومان"
    return f"{num:,} تومان"

def build_caption(form: dict, number: int, jdate: str) -> str:
    # ساخت کپشن زیبا
    parts = [
        "🚗 <b>آگهی جدید</b>",
        f"📌 <b>دسته:</b> {html.quote(form['category'])}",
        f"🏷️ <b>نام خودرو:</b> {html.quote(form['car'])}",
        f"📅 <b>سال ساخت:</b> {html.quote(form['year'])}",
        f"🎨 <b>رنگ:</b> {html.quote(form['color'])}",
        f"📍 <b>شهر:</b> {html.quote(form.get('city') or '—')}",
        f"⚙️ <b>گیربکس:</b> {html.quote(form.get('gear') or '—')}",
        f"🛡️ <b>مهلت بیمه:</b> {html.quote(form.get('insurance') or '—')}",
        f"📈 <b>کارکرد:</b> {html.quote(form['km'])} کیلومتر",
    ]
    if form.get("price_words"):
        parts.append(f"💵 <b>قیمت:</b> {html.quote(form['price_words'])}")
    if form.get("desc"):
        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")

    # ردیف پایانی: تاریخ و شماره
    parts.append(f"\n🗓️ <i>{jdate}</i>  •  🔷 <b>#{number}</b>")
    return "\n".join(parts)

# /start → فقط دکمه
@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است.")
        return
    await message.answer("برای ثبت آگهی دکمه زیر را بزنید:", reply_markup=start_keyboard(SETTINGS.WEBAPP_URL))

# تبدیل و اعتبارسنجی داده‌های دریافتی از WebApp
def validate_and_normalize(payload: dict) -> tuple[bool, str|None, dict|None]:
    cat   = (payload.get("category") or "").strip()               # فروش/فروش همکاری/خرید
    car   = (payload.get("car") or "").strip()
    year  = (payload.get("year") or "").strip()
    color = (payload.get("color") or "").strip()
    km    = (payload.get("km") or "").strip()
    price_raw = (payload.get("price") or "").strip()
    city  = (payload.get("city") or "").strip()
    ins   = (payload.get("insurance") or "").strip()
    gear  = (payload.get("gear") or "").strip()
    desc  = (payload.get("desc") or "").strip()

    # نام خودرو: حداکثر 10، بیشتر از 4 رقم پشت سرهم ممنوع
    if not car or len(car) > 10 or re.search(r"\d{5,}", car):
        return False, "نام خودرو نامعتبر است (حداکثر ۱۰ کاراکتر، بیش از ۴ رقم پشت‌سرهم ممنوع).", None

    # سال ساخت: 4 رقم
    if not re.fullmatch(r"\d{4}", year):
        return False, "سال ساخت باید ۴ رقم باشد.", None

    # رنگ: فقط حروف فارسی، حداکثر 6
    if not re.fullmatch(r"[آ-ی\s]{1,6}", color):
        return False, "رنگ باید حروف فارسی (حداکثر ۶ کاراکتر) باشد.", None

    # کارکرد: 5 رقم
    if not re.fullmatch(r"\d{1,5}", km):
        return False, "کارکرد باید عددی حداکثر ۵ رقمی باشد.", None

    # قیمت: در «فروش همکاری» اختیاری/بی‌اثر؛ در فروش و خرید حداکثر 5 رقم
    price_num = None
    price_words = None
    if cat != "فروش همکاری":
        if not re.fullmatch(r"\d{1,5}", price_raw):
            return False, "قیمت باید عددی حداکثر ۵ رقمی باشد.", None
        price_num = int(price_raw)
        price_words = fmt_price_to_words(price_num)

    form = {
        "category": cat,
        "car": car,
        "year": year,
        "color": color,
        "km": km,
        "city": city,
        "insurance": ins,
        "gear": gear,
        "desc": desc,
        "price_num": price_num,
        "price_words": price_words,
        "username": "",
        "photos": [],   # بعداً پر می‌شود
    }
    return True, None, form

@router.message(F.web_app_data)
async def on_webapp_payload(message: types.Message):
    try:
        payload = json.loads(message.web_app_data.data or "{}")
    except Exception:
        payload = {}

    ok, err, form = validate_and_normalize(payload)
    if not ok:
        await message.answer(err or "داده نامعتبر است.")
        return

    form["username"] = message.from_user.username or ""

    # توکن، ذخیره و راهنمای ارسال عکس
    token = uuid4().hex
    PENDING[token] = {"form": form, "user_id": message.from_user.id}
    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": 5}

    await message.answer(
        "فرم شما ذخیره شد ✅\n"
        "حالا حداکثر ۵ عکس ارسال کنید (همین‌جا). وقتی تمام شد دستور /done را بفرستید."
    )

# جمع‌آوری عکس‌ها
@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess:
        return
    token = sess["token"]
    remain = sess["remain"]
    if remain <= 0:
        await message.reply("حداکثر ۵ عکس مجاز است. /done")
        return
    # بزرگ‌ترین سایز
    file_id = message.photo[-1].file_id
    PENDING[token]["form"]["photos"].append(file_id)
    sess["remain"] -= 1
    await message.reply(f"عکس ثبت شد. باقی مانده: {sess['remain']}")

# پایان جمع‌آوری عکس‌ها
@router.message(Command("done"))
async def on_done(message: types.Message):
    sess = PHOTO_WAIT.pop(message.from_user.id, None)
    if not sess:
        await message.reply("چیزی برای ثبت ندارید.")
        return
    token = sess["token"]
    data = PENDING.get(token)
    if not data:
        await message.reply("جلسه یافت نشد.")
        return

    form = data["form"]

    # مسیر انتشار بسته به دسته
    if form["category"] in ("فروش", "خرید"):
        # مستقیم به گروه
        await publish_to_group(message, form)
        await message.reply("✅ آگهی شما منتشر شد.")
        PENDING.pop(token, None)
    else:
        # فروش همکاری → برای ادمین بفرست با دکمه‌های ادیت/انتشار
        txt = admin_preview_text(form, message.from_user)
        kb = admin_review_kb(token)
        for admin_id in SETTINGS.ADMIN_IDS:
            try:
                if form["photos"]:
                    # به ادمین فقط متن می‌فرستیم (برای بازبینی سریع)
                    await message.bot.send_message(admin_id, txt, reply_markup=kb)
                else:
                    await message.bot.send_message(admin_id, txt, reply_markup=kb)
            except Exception:
                pass
        await message.reply("فرم شما برای ادمین ارسال شد ✅")

def admin_preview_text(form: dict, user: types.User) -> str:
    parts = [
        "🧾 <b>پیش‌نمایش فروش همکاری</b>",
        f"نام خودرو: {html.quote(form['car'])}",
        f"سال: {html.quote(form['year'])}",
        f"رنگ: {html.quote(form['color'])}",
        f"کارکرد: {html.quote(form['km'])}",
        f"شهر: {html.quote(form.get('city') or '—')}",
        f"گیربکس: {html.quote(form.get('gear') or '—')}",
        f"بیمه: {html.quote(form.get('insurance') or '—')}",
        f"قیمت (قابل‌ویرایش): {html.quote(form.get('price_words') or '—')}",
        f"توضیحات (قابل‌ویرایش): {html.quote(form.get('desc') or '—')}",
        f"کاربر: {html.quote(user.full_name)} (id={user.id})"
    ]
    return "\n".join(parts)

async def publish_to_group(message: types.Message, form: dict):
    # شماره روزانه + تاریخ جلالی
    num, iso = next_daily_number()
    jdate = to_jalali(iso)
    caption = build_caption(form, num, jdate)

    photos = form.get("photos") or []
    if photos:
        # آلبوم: کپشن فقط روی اولین عکس
        mg = MediaGroupBuilder(caption=caption)
        mg.add_photo(media=photos[0])
        for fid in photos[1:5]:
            mg.add_photo(media=fid)
        await message.bot.send_media_group(SETTINGS.TARGET_GROUP_ID, media=mg.build())
    else:
        await message.bot.send_message(SETTINGS.TARGET_GROUP_ID, caption)

# ادمین: ویرایش قیمت/توضیحات/انتشار/رد
@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}
    await call.message.reply("قیمت جدید را به صورت عدد (حداکثر ۵ رقم) بفرستید.")
    await call.answer()

@router.callback_query(F.data.startswith("edit_desc:"))
async def cb_edit_desc(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "desc"}
    await call.message.reply("توضیحات جدید را بفرستید.")
    await call.answer()

@router.message(F.text, ~CommandStart())
async def on_admin_text_edit(message: types.Message):
    w = ADMIN_EDIT_WAIT.get(message.from_user.id)
    if not w: 
        return
    token, field = w["token"], w["field"]
    info = PENDING.get(token)
    if not info:
        await message.reply("درخواست یافت نشد."); ADMIN_EDIT_WAIT.pop(message.from_user.id, None); return
    form = info["form"]

    if field == "price":
        if not re.fullmatch(r"\d{1,5}", message.text.strip()):
            await message.reply("قیمت باید عددی حداکثر ۵ رقمی باشد.")
            return
        form["price_num"] = int(message.text.strip())
        form["price_words"] = fmt_price_to_words(form["price_num"])
        await message.reply(f"قیمت به «{form['price_words']}» تغییر کرد.")
    elif field == "desc":
        form["desc"] = message.text.strip()
        await message.reply("توضیحات به‌روزرسانی شد.")
    ADMIN_EDIT_WAIT.pop(message.from_user.id, None)

@router.callback_query(F.data.startswith("publish:"))
async def cb_publish(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    data = PENDING.pop(token, None)
    if not data:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    form = data["form"]

    # انتشار
    await publish_to_group(call.message, form)
    await call.answer("منتشر شد.")
    try:
        await call.message.edit_text(call.message.text + "\n\n✅ منتشر شد")
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    PENDING.pop(token, None)
    await call.answer("رد شد.")
    try:
        await call.message.edit_text(call.message.text + "\n\n❌ رد شد")
    except Exception:
        pass

# ادمین runtime
@router.message(Command("setadminkeyvan"))
async def cmd_set_admin(message: types.Message):
    EXTRA_ADMINS.add(message.from_user.id)
    await message.answer("شما به عنوان ادمین (runtime) ثبت شدید.")
