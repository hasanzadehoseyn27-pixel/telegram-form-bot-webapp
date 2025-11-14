import json, re
from uuid import uuid4
import jdatetime

from aiogram import Router, F, html, types
from aiogram import Bot
from aiogram.filters import CommandStart, Command
from aiogram.utils.media_group import MediaGroupBuilder

from .config import SETTINGS
from .keyboards import start_keyboard
from .storage import (
    next_daily_number,
    bootstrap_admins, list_admins, add_admin, remove_admin, is_admin
)

# بوت‌استرپ ادمین‌ها از .env + فایل + OWNER
bootstrap_admins(SETTINGS.ADMIN_IDS, SETTINGS.OWNER_ID)

router = Router()

PENDING: dict[str, dict] = {}         # token -> {form, user_id, grp:{...}, needs:{price,desc}}
PHOTO_WAIT: dict[int, dict] = {}      # user_id -> {token, remain}
ADMIN_EDIT_WAIT: dict[int, dict] = {} # admin_id -> {token, field}

def to_jalali(date_iso: str) -> str:
    y, m, d = map(int, date_iso.split("-"))
    j = jdatetime.date.fromgregorian(day=d, month=m, year=y)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"

def price_words(num: int) -> str:
    if num >= 100_000_000_000:
        num = 100_000_000_000
    parts = []
    if num >= 1_000_000_000:
        b = num // 1_000_000_000
        parts.append(f"{b} میلیارد")
        num %= 1_000_000_000
    if num >= 1_000_000:
        m = num // 1_000_000
        parts.append(f"{m} میلیون")
        num %= 1_000_000
    if num >= 1_000:
        k = num // 1_000
        parts.append(f"{k} هزار")
        num %= 1_000
    if num > 0:
        parts.append(f"{num}")
    return " و ".join(parts) + " تومان"

def build_caption(form: dict, number: int, jdate: str, *, show_price: bool, show_desc: bool) -> str:
    parts = [
        "🚗 <b>آگهی جدید</b>",
        f"🏷️ <b>نام خودرو:</b> {html.quote(form['car'])}",
        f"📅 <b>سال ساخت:</b> {html.quote(form['year'])}",
        f"🎨 <b>رنگ:</b> {html.quote(form['color'])}",
        f"📍 <b>شهر:</b> {html.quote(form.get('city') or '—')}",
        f"⚙️ <b>گیربکس:</b> {html.quote(form.get('gear') or '—')}",
        f"🛡️ <b>مهلت بیمه:</b> {html.quote(form.get('insurance') or '—')}",
        f"📈 <b>کارکرد:</b> {html.quote(form['km'])} کیلومتر",
    ]
    if show_price and form.get("price_words"):
        parts.append(f"💵 <b>قیمت:</b> {html.quote(form['price_words'])}")
    if show_desc and (form.get("desc") or "").strip():
        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")

    # ردیف تماس (قبل از تاریخ و شماره)
    parts.append("📞 شماره تماس: 09127475355 - کیوان")
    parts.append(f"\n🗓️ <i>{jdate}</i>  •  🔷 <b>#{number}</b>")
    return "\n".join(parts)

def admin_caption(form: dict, number: int, jdate: str) -> str:
    lines = ["🧪 <b>موارد نیازمند ویرایش/تایید:</b>"]
    lines.append(f"📝 <b>توضیحات پیشنهادی:</b>\n{html.quote(form.get('desc') or '—')}")
    if form.get("category") == "فروش همکاری":
        lines.append(f"💵 <b>قیمت پیشنهادی:</b> {html.quote(form.get('price_words') or '—')}")
    lines.append("—" * 10)
    lines.append("📋 <b>خلاصه آگهی</b>")
    lines.append(f"دسته: {html.quote(form['category'])}")
    lines.append(f"نام خودرو: {html.quote(form['car'])}")
    lines.append(f"سال/رنگ/کارکرد: {html.quote(form['year'])} / {html.quote(form['color'])} / {html.quote(form['km'])}km")
    lines.append(f"شهر/گیربکس/بیمه: {html.quote(form.get('city') or '—')} / {html.quote(form.get('gear') or '—')} / {html.quote(form.get('insurance') or '—')}")
    lines.append(f"\n🗓️ <i>{jdate}</i>  •  🔷 <b>#{number}</b>")
    return "\n".join(lines)

# ---------- استارت ----------
@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است.")
        return
    owner = (message.from_user.id == SETTINGS.OWNER_ID)
    kb = start_keyboard(
        SETTINGS.WEBAPP_URL,
        is_owner=owner,
        admin_url=SETTINGS.ADMIN_WEBAPP_URL if owner else None
    )
    await message.answer("خوش آمدید. گزینه مورد نظر را انتخاب کنید:", reply_markup=kb)

@router.message(Command("id", "ids"))
async def cmd_ids(message: types.Message):
    await message.answer(f"your user_id: {message.from_user.id}\nchat_id: {message.chat.id}\nchat_type: {message.chat.type}")

@router.message(Command("admins"))
async def cmd_admins(message: types.Message):
    admins = list_admins()
    txt = "ادمین‌ها:\n" + ("\n".join(map(str, admins)) if admins else "— خالی —")
    await message.answer(txt)

# ---------- وب‌اپ: فرم + پنل مدیریتی ----------
def validate_and_normalize(payload: dict) -> tuple[bool, str|None, dict|None]:
    cat   = (payload.get("category") or "").strip()
    if not cat:
        return False, "bad", None  # برای وب‌اپ ادمین استفاده نمی‌شود
    car   = (payload.get("car") or "").strip()
    year  = (payload.get("year") or "").strip()
    color = (payload.get("color") or "").strip()
    km    = (payload.get("km") or "").strip()
    price_raw = (payload.get("price") or "").strip()  # همه‌ی دسته‌ها امکان ورود قیمت
    city  = (payload.get("city") or "").strip()
    ins   = (payload.get("insurance") or "").strip()
    gear  = (payload.get("gear") or "").strip()
    desc  = (payload.get("desc") or "").strip()

    if not car or len(car) > 10 or re.search(r"\d{5,}", car):
        return False, "نام خودرو نامعتبر است.", None
    if not re.fullmatch(r"\d{4}", year):
        return False, "سال ساخت باید ۴ رقم باشد.", None
    if not re.fullmatch(r"[آ-ی\s]{1,6}", color):
        return False, "رنگ باید حروف فارسی (حداکثر ۶) باشد.", None
    if not re.fullmatch(r"\d{1,6}", km):
        return False, "کارکرد باید عددی حداکثر ۶ رقمی باشد.", None

    num = int(re.sub(r"\D", "", price_raw or "0") or "0")
    price_num = None
    price_words_str = None

    if cat == "فروش همکاری":
        if num > 0:
            if num > 100_000_000_000:
                num = 100_000_000_000
            price_num = num
            price_words_str = price_words(num)
    else:
        if num < 1 or num > 100_000_000_000:
            return False, "قیمت باید عددی معتبر تا سقف ۱۰۰ میلیارد تومان باشد.", None
        price_num = num
        price_words_str = price_words(num)

    form = {
        "category": cat, "car": car, "year": year, "color": color, "km": km,
        "city": city, "insurance": ins, "gear": gear, "desc": desc,
        "price_num": price_num, "price_words": price_words_str,
        "username": "", "photos": [],
    }
    return True, None, form

@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    # اکشن‌های پنل مدیریتی نیز از طریق وب‌اپ می‌آید
    try:
        data = json.loads(message.web_app_data.data or "{}")
    except Exception:
        data = {}

    action = (data.get("action") or "").strip()

    # ----- بخش پنل مدیریتی (فقط OWNER) -----
    if action.startswith("admin:"):
        if message.from_user.id != SETTINGS.OWNER_ID:
            await message.answer("دسترسی مدیریت فقط برای ادمین اصلی است.")
            return

        if action == "admin:add":
            uid = int(str(data.get("user_id") or "0"))
            if uid <= 0:
                await message.answer("user_id نامعتبر است.")
                return
            created = add_admin(uid)
            if created:
                await message.answer(f"✅ {uid} به ادمین‌ها اضافه شد.")
                # پیام اطلاع
                try:
                    await message.bot.send_message(uid, "شما به عنوان ادمین ثبت شدید ✅")
                except Exception:
                    pass
            else:
                await message.answer("این کاربر قبلاً ادمین بوده است.")
            return

        if action == "admin:remove":
            uid = int(str(data.get("user_id") or "0"))
            if uid <= 0:
                await message.answer("user_id نامعتبر است.")
                return
            ok = remove_admin(uid)
            if ok:
                await message.answer(f"❌ ادمین {uid} حذف شد.")
                try:
                    await message.bot.send_message(uid, "دسترسی ادمین شما حذف شد ❌")
                except Exception:
                    pass
            else:
                await message.answer("حذف انجام نشد (ممکن است ادمین نبوده یا OWNER باشد).")
            return

        if action == "admin:list":
            admins = list_admins()
            await message.answer("ادمین‌ها:\n" + ("\n".join(map(str, admins)) if admins else "— خالی —"))
            return

        # اکشن ناشناس
        await message.answer("اکشن مدیریتی نامعتبر است.")
        return

    # ----- بخش فرم آگهی -----
    ok, err, form = validate_and_normalize(data)
    if not ok:
        await message.answer(err or "داده نامعتبر است.")
        return

    form["username"] = message.from_user.username or ""

    token = uuid4().hex
    PENDING[token] = {"form": form, "user_id": message.from_user.id}
    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": 5}

    await message.answer(
        "فرم شما ذخیره شد ✅\n"
        "اگر عکس دارید تا ۵ عکس بفرستید و در پایان /done. اگر عکس ندارید همین حالا /done."
    )

@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess:
        return
    if sess["remain"] <= 0:
        await message.reply("حداکثر ۵ عکس مجاز است. /done")
        return
    file_id = message.photo[-1].file_id
    token = sess["token"]
    PENDING[token]["form"]["photos"].append(file_id)
    sess["remain"] -= 1
    await message.reply(f"عکس ثبت شد. باقی‌مانده: {sess['remain']}")

async def publish_to_group(message: types.Message, form: dict, *, show_price: bool, show_desc: bool):
    number, iso = next_daily_number()
    j = to_jalali(iso)
    caption = build_caption(form, number, j, show_price=show_price, show_desc=show_desc)
    photos = form.get("photos") or []

    if photos:
        mg = MediaGroupBuilder()
        mg.add_photo(media=photos[0], caption=caption, parse_mode="HTML")
        for fid in photos[1:5]:
            mg.add_photo(media=fid)
        msgs = await message.bot.send_media_group(SETTINGS.TARGET_GROUP_ID, media=mg.build())
        first = msgs[0]
        return {"chat_id": first.chat.id, "msg_id": first.message_id, "has_photos": True, "number": number, "jdate": j}
    else:
        msg = await message.bot.send_message(SETTINGS.TARGET_GROUP_ID, caption, parse_mode="HTML")
        return {"chat_id": msg.chat.id, "msg_id": msg.message_id, "has_photos": False, "number": number, "jdate": j}

async def send_review_to_admins(bot: Bot, form: dict, token: str, photos: list[str], grp: dict):
    admins = list_admins()
    if not admins:
        return 0
    cap = (
        "⚙️ <b>پنل بررسی</b>\n"
        "— ابتدا موارد ویرایش —\n"
        f"📝 توضیحات:\n{html.quote(form.get('desc') or '—')}\n" +
        (f"💵 قیمت: {html.quote(form.get('price_words') or '—')}\n" if form.get("category") == "فروش همکاری" else "") +
        ("—" * 10) + "\n" +
        admin_caption(form, grp.get("number"), grp.get("jdate"))
    )
    ok = 0
    for admin_id in admins:
        try:
            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=cap, parse_mode="HTML")
                for fid in photos[1:5]:
                    mg.add_photo(media=fid)
                await bot.send_media_group(admin_id, media=mg.build())
            else:
                await bot.send_message(admin_id, cap, parse_mode="HTML")
            # دکمه‌ها
            from .keyboards import admin_review_kb  # اگر قبلاً داشتی؛ در این نسخه حذف نشده
        except Exception:
            pass
        try:
            await bot.send_message(admin_id, "ویرایش/اعمال:", reply_markup=admin_review_kb(token))
            ok += 1
        except Exception:
            pass
    return ok

@router.message(Command("done"))
async def on_done(message: types.Message):
    sess = PHOTO_WAIT.pop(message.from_user.id, None)
    if not sess:
        await message.reply("جلسه‌ای برای عکس فعال نیست.")
        return

    token = sess["token"]
    info = PENDING.get(token)
    if not info:
        await message.reply("درخواست یافت نشد.")
        return

    form = info["form"]
    show_price = form["category"] != "فروش همکاری"
    show_desc  = False
    grp = await publish_to_group(message, form, show_price=show_price, show_desc=show_desc)

    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": (form["category"] == "فروش همکاری"), "desc": True}

    sent = await send_review_to_admins(message.bot, form, token, form.get("photos") or [], grp)

    await message.reply("پست اولیه منتشر شد ✅ و برای ادمین ارسال گردید." if sent else
                        "پست اولیه منتشر شد ✅ اما ادمینی تنظیم/دریافت نشد.")

# ویرایش/اعمال و رد همان نسخه قبلی شماست (برای اختصار حذف نشده)
from aiogram.filters import Command as _C  # جلوگیری از تداخل
@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}
    await call.message.reply("قیمت جدید را عددی بفرستید. (تا سقف ۱۰۰ میلیارد)")
    await call.answer()

@router.callback_query(F.data.startswith("edit_desc:"))
async def cb_edit_desc(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "desc"}
    await call.message.reply("متن جدید توضیحات را بفرستید.")
    await call.answer()

@router.message(F.text, ~CommandStart())
async def on_admin_text_edit(message: types.Message):
    w = ADMIN_EDIT_WAIT.get(message.from_user.id)
    if not w:
        return
    token, field = w["token"], w["field"]
    info = PENDING.get(token)
    if not info:
        ADMIN_EDIT_WAIT.pop(message.from_user.id, None)
        await message.reply("درخواست یافت نشد.")
        return
    form = info["form"]

    if field == "price":
        t = message.text.strip()
        num = int(re.sub(r"\D", "", t or "0") or "0")
        if num < 1 or num > 100_000_000_000:
            await message.reply("قیمت نامعتبر است. (تا سقف ۱۰۰ میلیارد)")
            return
        form["price_num"] = num
        form["price_words"] = price_words(num)
        await message.reply(f"قیمت به «{form['price_words']}» تغییر کرد.")
    elif field == "desc":
        form["desc"] = message.text.strip()
        await message.reply("توضیحات به‌روزرسانی شد.")

    ADMIN_EDIT_WAIT.pop(message.from_user.id, None)

@router.callback_query(F.data.startswith("publish:"))
async def cb_publish(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    info = PENDING.get(token)
    if not info:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    form = info["form"]
    grp  = info.get("grp") or {}
    needs = info.get("needs") or {"price": False, "desc": True}
    number = grp.get("number")
    jdate  = grp.get("jdate")
    if not number or not jdate:
        n, iso = next_daily_number()
        number, jdate = n, to_jalali(iso)
    show_price = not needs.get("price", False) or bool(form.get("price_words"))
    show_desc  = not needs.get("desc", False)  or bool(form.get("desc"))
    caption = build_caption(form, number, jdate, show_price=show_price, show_desc=show_desc)
    try:
        if grp.get("has_photos"):
            await call.bot.edit_message_caption(chat_id=grp["chat_id"], message_id=grp["msg_id"], caption=caption, parse_mode="HTML")
        else:
            await call.bot.edit_message_text(chat_id=grp["chat_id"], message_id=grp["msg_id"], text=caption, parse_mode="HTML")
    except Exception:
        await call.answer("خطا در ویرایش پست گروه.", show_alert=True); return
    try:
        await call.message.edit_text(call.message.text + "\n\n✅ اعمال شد روی پست گروه")
    except Exception:
        pass
    await call.answer("اعمال شد.")
    PENDING.pop(token, None)

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    PENDING.pop(token, None)
    await call.answer("رد شد.")
    try:
        await call.message.edit_text(call.message.text + "\n\n❌ رد شد")
    except Exception:
        pass
