import json, re
from uuid import uuid4
from datetime import datetime
import jdatetime

from aiogram import Router, F, html, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.media_group import MediaGroupBuilder

from .config import SETTINGS
from .keyboards import start_keyboard, admin_review_kb
from .storage import next_daily_number

router = Router()

PENDING: dict[str, dict] = {}          # token -> {form, user_id}
PHOTO_WAIT: dict[int, dict] = {}       # user_id -> {token, remain}
ADMIN_EDIT_WAIT: dict[int, dict] = {}  # admin_id -> {token, field}
EXTRA_ADMINS: set[int] = set()

def is_admin(uid: int) -> bool:
    return uid in SETTINGS.ADMIN_IDS or uid in EXTRA_ADMINS

def to_jalali(date_iso: str) -> str:
    y,m,d = map(int, date_iso.split("-"))
    j = jdatetime.date.fromgregorian(day=d, month=m, year=y)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"

def fmt_price_to_words(num: int) -> str:
    if num >= 1_000_000_000: return f"{num//1_000_000_000} میلیارد تومان"
    if num >= 1_000_000:     return f"{num//1_000_000} میلیون تومان"
    if num >= 1_000:         return f"{(num//1000)*1000:,} تومان"
    return f"{num:,} تومان"

def build_caption(form: dict, number: int, jdate: str) -> str:
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
    if form.get("price_words"): parts.append(f"💵 <b>قیمت:</b> {html.quote(form['price_words'])}")
    if form.get("desc"):        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")
    parts.append(f"\n🗓️ <i>{jdate}</i>  •  🔷 <b>#{number}</b>")
    return "\n".join(parts)

@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است."); return
    await message.answer("برای ثبت آگهی دکمه زیر را بزنید:", reply_markup=start_keyboard(SETTINGS.WEBAPP_URL))

def validate_and_normalize(payload: dict) -> tuple[bool, str|None, dict|None]:
    if payload.get("action") == "open_admin":
        return False, "admin_open", None  # هندل می‌کنیم

    cat   = (payload.get("category") or "").strip()
    car   = (payload.get("car") or "").strip()
    year  = (payload.get("year") or "").strip()
    color = (payload.get("color") or "").strip()
    km    = (payload.get("km") or "").strip()
    price_raw = (payload.get("price") or "").strip()
    city  = (payload.get("city") or "").strip()
    ins   = (payload.get("insurance") or "").strip()
    gear  = (payload.get("gear") or "").strip()
    desc  = (payload.get("desc") or "").strip()

    if not car or len(car)>10 or re.search(r"\d{5,}", car):
        return False, "نام خودرو نامعتبر است.", None
    if not re.fullmatch(r"\d{4}", year):
        return False, "سال ساخت باید ۴ رقم باشد.", None
    if not re.fullmatch(r"[آ-ی\s]{1,6}", color):
        return False, "رنگ باید حروف فارسی (حداکثر ۶) باشد.", None
    if not re.fullmatch(r"\d{1,5}", km):
        return False, "کارکرد باید عددی حداکثر ۵ رقمی باشد.", None

    price_num = None; price_words = None
    if cat != "فروش همکاری":
        if price_raw and not re.fullmatch(r"\d{1,5}", price_raw):
            return False, "قیمت باید عددی حداکثر ۵ رقمی باشد.", None
        if price_raw:
            price_num = int(price_raw)
            price_words = fmt_price_to_words(price_num)

    form = {
        "category": cat, "car": car, "year": year, "color": color, "km": km,
        "city": city, "insurance": ins, "gear": gear, "desc": desc,
        "price_num": price_num, "price_words": price_words,
        "username": "", "photos": [],
    }
    return True, None, form

@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data or "{}")
    except Exception:
        data = {}

    ok, err, form = validate_and_normalize(data)
    if not ok:
        if err == "admin_open":
            await message.answer("پنل مدیریتی به‌زودی اضافه می‌شود.")
        else:
            await message.answer(err or "داده نامعتبر است.")
        return

    form["username"] = message.from_user.username or ""

    token = uuid4().hex
    PENDING[token] = {"form": form, "user_id": message.from_user.id}
    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": 5}

    await message.answer(
        "فرم شما ذخیره شد ✅\n"
        "اگر می‌خواهید عکس هم اضافه کنید، تا ۵ عکس بفرستید و در پایان /done.\n"
        "اگر عکس ندارید، همین حالا /done را بفرستید."
    )

@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess: return
    if sess["remain"] <= 0:
        await message.reply("حداکثر ۵ عکس مجاز است. /done"); return
    file_id = message.photo[-1].file_id
    token = sess["token"]
    PENDING[token]["form"]["photos"].append(file_id)
    sess["remain"] -= 1
    await message.reply(f"عکس ثبت شد. باقی‌مانده: {sess['remain']}")

@router.message(Command("done"))
async def on_done(message: types.Message):
    sess = PHOTO_WAIT.pop(message.from_user.id, None)
    if not sess:
        await message.reply("جلسه‌ای برای ارسال عکس فعال نیست."); return

    token = sess["token"]; data = PENDING.get(token)
    if not data:
        await message.reply("درخواست یافت نشد."); return

    form = data["form"]
    if form["category"] in ("فروش", "خرید"):
        await publish_to_group(message, form)
        PENDING.pop(token, None)
        await message.reply("✅ آگهی شما منتشر شد.")
    else:
        txt = admin_preview_text(form, message.from_user)
        kb = admin_review_kb(token)
        for admin_id in SETTINGS.ADMIN_IDS:
            try: await message.bot.send_message(admin_id, txt, reply_markup=kb)
            except Exception: pass
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
    num, iso = next_daily_number()
    caption = build_caption(form, num, to_jalali(iso))
    photos = form.get("photos") or []
    if photos:
        mg = MediaGroupBuilder(caption=caption)
        mg.add_photo(media=photos[0])
        for fid in photos[1:5]: mg.add_photo(media=fid)
        await message.bot.send_media_group(SETTINGS.TARGET_GROUP_ID, media=mg.build())
    else:
        await message.bot.send_message(SETTINGS.TARGET_GROUP_ID, caption)

@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    if token not in PENDING: await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}
    await call.message.reply("قیمت جدید را به صورت عدد (حداکثر ۵ رقم) بفرستید."); await call.answer()

@router.callback_query(F.data.startswith("edit_desc:"))
async def cb_edit_desc(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    if token not in PENDING: await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "desc"}
    await call.message.reply("توضیحات جدید را بفرستید."); await call.answer()

@router.message(F.text, ~CommandStart())
async def on_admin_text_edit(message: types.Message):
    w = ADMIN_EDIT_WAIT.get(message.from_user.id)
    if not w: return
    token, field = w["token"], w["field"]
    info = PENDING.get(token)
    if not info: ADMIN_EDIT_WAIT.pop(message.from_user.id, None); await message.reply("درخواست یافت نشد."); return
    form = info["form"]

    if field == "price":
        t = message.text.strip()
        if not re.fullmatch(r"\d{1,5}", t): await message.reply("قیمت باید عددی حداکثر ۵ رقمی باشد."); return
        form["price_num"] = int(t); form["price_words"] = fmt_price_to_words(form["price_num"])
        await message.reply(f"قیمت به «{form['price_words']}» تغییر کرد.")
    elif field == "desc":
        form["desc"] = message.text.strip()
        await message.reply("توضیحات به‌روزرسانی شد.")
    ADMIN_EDIT_WAIT.pop(message.from_user.id, None)

@router.callback_query(F.data.startswith("publish:"))
async def cb_publish(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    data = PENDING.pop(token, None)
    if not data: await call.answer("درخواست یافت نشد.", show_alert=True); return
    await publish_to_group(call.message, data["form"])
    await call.answer("منتشر شد.")
    try: await call.message.edit_text(call.message.text + "\n\n✅ منتشر شد")
    except Exception: pass

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":",1)[1]
    PENDING.pop(token, None)
    await call.answer("رد شد.")
    try: await call.message.edit_text(call.message.text + "\n\n❌ رد شد")
    except Exception: pass

@router.message(Command("setadminkeyvan"))
async def cmd_set_admin(message: types.Message):
    EXTRA_ADMINS.add(message.from_user.id)
    await message.answer("شما به عنوان ادمین (runtime) ثبت شدید.")
