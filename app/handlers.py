
import json, re
from uuid import uuid4
import jdatetime

from aiogram import Router, F, html, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.utils.media_group import MediaGroupBuilder

from .config import SETTINGS
from .keyboards import start_keyboard, admin_menu_kb, admin_review_kb, user_finish_kb
from .storage import (
    next_daily_number, list_admins, add_admin, remove_admin, is_admin,
    list_destinations, add_destination, remove_destination,
    set_active_destination, get_active_destination, get_active_id_and_title
)

router = Router()

# ثوابت
MAX_PHOTOS = 5

# حافظه‌ی موقت
PENDING: dict[str, dict] = {}           # token -> {form, user_id, grp:{...}, needs:{price,desc}, admin_msgs:[(chat_id,msg_id),...]}
PHOTO_WAIT: dict[int, dict] = {}        # user_id -> {token, remain}
ADMIN_EDIT_WAIT: dict[int, dict] = {}   # admin_id -> {token, field}
ADMIN_WAIT_INPUT: dict[int, dict] = {}  # admin_id -> {mode: add/remove}

# ---------- کمکی ----------
def to_jalali(date_iso: str) -> str:
    y, m, d = map(int, date_iso.split("-"))
    j = jdatetime.date.fromgregorian(year=y, month=m, day=d)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"

def contains_persian_digits(s: str) -> bool:
    return bool(re.search(r"[\u06F0-\u06F9\u0660-\u0669]", s or ""))

def price_words(num: int) -> str:
    if num >= 100_000_000_000:
        num = 100_000_000_000
    parts = []
    if num >= 1_000_000_000:
        b = num // 1_000_000_000
        parts.append(f"{b} میلیارد"); num %= 1_000_000_000
    if num >= 1_000_000:
        m = num // 1_000_000; parts.append(f"{m} میلیون"); num %= 1_000_000
    if num >= 1_000:
        k = num // 1_000; parts.append(f"{k} هزار"); num %= 1_000
    if num > 0:
        parts.append(f"{num}")
    return " و ".join(parts) + " تومان"

def build_caption(form: dict, number: int, jdate: str, *, show_price: bool, show_desc: bool) -> str:
    parts = [
        f"🔷 <b>شماره آگهی: {number}</b>",
        "🚗 <b>آگهی جدید</b>",
        f"🏷 <b>نام خودرو:</b> {html.quote(form['car'])}",
        f"📅 <b>سال ساخت:</b> {html.quote(form['year'])}",
        f"🎨 <b>رنگ:</b> {html.quote(form['color'])}",
        f"⚙️ <b>گیربکس:</b> {html.quote(form.get('gear') or '—')}",
        f"🛡 <b>مهلت بیمه:</b> {html.quote(form.get('insurance') or '—')}",
        f"📈 <b>کارکرد:</b> {html.quote(form['km'])} کیلومتر",
    ]
    if show_price and form.get("price_words"):
        parts.append(f"💵 <b>قیمت:</b> {html.quote(form['price_words'])}")
    if show_desc and (form.get("desc") or "").strip():
        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")

    parts.append("📞 شماره تماس: 09127475355 - کیوان")
    parts.append(f"\n🗓 <i>{jdate}</i>")
    return "\n".join(parts)

def admin_caption(form: dict, number: int, jdate: str) -> str:
    lines = ["🧪 <b>موارد نیازمند ویرایش/تایید:</b>"]
    # هر دو مورد را همیشه نشان بده
    lines.append(f"💵 <b>قیمت پیشنهادی:</b> {html.quote(form.get('price_words') or '—')}")
    lines.append(f"📝 <b>توضیحات پیشنهادی:</b>\n{html.quote(form.get('desc') or '—')}")
    lines.append("—" * 10)
    lines.append("📋 <b>خلاصه آگهی</b>")
    lines.append(f"دسته: {html.quote(form['category'])}")
    lines.append(f"نام خودرو: {html.quote(form['car'])}")
    lines.append(f"سال/رنگ/کارکرد: {html.quote(form['year'])} / {html.quote(form['color'])} / {html.quote(form['km'])}km")
    lines.append(f"گیربکس/بیمه: {html.quote(form.get('gear') or '—')} / {html.quote(form.get('insurance') or '—')}")
    lines.append(f"\n🗓 <i>{jdate}</i>  •  🔷 <b>#{number}</b>")
    return "\n".join(lines)

# ---------- شروع و منو ----------
@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است."); return
    kb = start_keyboard(SETTINGS.WEBAPP_URL, is_admin(message.from_user.id))
    await message.answer("برای ثبت آگهی، دکمه زیر را بزنید:", reply_markup=kb)

@router.message(F.text == "⚙️ پنل مدیریتی")
async def open_admin_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("این بخش فقط برای ادمین‌هاست."); return
    await message.answer("پنل مدیریتی:", reply_markup=None)
    await message.answer("یک گزینه را انتخاب کنید:", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "admin:list")
async def admin_list_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    admins = list_admins()
    txt = "ادمین‌های فعلی:\n" + ("\n".join(map(str, admins)) if admins else "— خالی —")
    await call.message.answer(txt)
    await call.answer()

@router.callback_query(F.data == "admin:add")
async def admin_add_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "add"}
    await call.message.answer("آیدی عددی کاربر را ارسال کنید تا ادمین شود:")
    await call.answer()

@router.callback_query(F.data == "admin:remove")
async def admin_remove_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "remove"}
    await call.message.answer("آیدی عددی ادمین را ارسال کنید تا حذف شود (OWNER حذف نمی‌شود):")
    await call.answer()

@router.message(F.text.regexp(r"^\d{4,}$"))
async def admin_id_input(message: types.Message):
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w or not is_admin(message.from_user.id):
        return
    uid = int(message.text.strip())
    mode = w["mode"]
    if mode == "add":
        ok = add_admin(uid)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")
    elif mode == "remove":
        ok = remove_admin(uid)
        await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف نیست/یافت نشد.")
    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

# ---------- کمک / عیب‌یابی ----------
@router.message(Command("id", "ids"))
async def cmd_id(message: types.Message):
    await message.answer(f"user_id: {message.from_user.id}\nchat_id: {message.chat.id}\nchat_type: {message.chat.type}")

@router.message(Command("admins"))
async def cmd_admins(message: types.Message):
    admins = list_admins()
    txt = "ادمین‌های فعلی:\n" + ("\n".join(map(str, admins)) if admins else "— خالی —")
    await message.answer(txt)

# ---------- اعتبارسنجی فرم ----------
def validate_and_normalize(payload: dict) -> tuple[bool, str|None, dict|None]:
    cat   = (payload.get("category") or "").strip()
    car   = (payload.get("car") or "").strip()
    year  = (payload.get("year") or "").strip()
    color = (payload.get("color") or "").strip()
    km    = (payload.get("km") or "").strip()
    price_raw = (payload.get("price") or "").strip()  # فروش همکاری اختیاری
    ins   = (payload.get("insurance") or "").strip()
    gear  = (payload.get("gear") or "").strip()
    desc  = (payload.get("desc") or "").strip()

    # ممنوع بودن ارقام فارسی حتی داخل car
    if contains_persian_digits(car) or contains_persian_digits(year) or contains_persian_digits(km) or contains_persian_digits(price_raw):
        return False, "لطفاً اعداد را فقط با رقم‌های لاتین (0-9) وارد کنید.", None

    if not car or len(car) > 10 or re.search(r"\d{5,}", car):
        return False, "نام خودرو نامعتبر است.", None
    if not re.fullmatch(r"[0-9]{4}", year):
        return False, "سال ساخت باید ۴ رقم لاتین باشد.", None
    if not re.fullmatch(r"[آ-ی\s]{1,6}", color):
        return False, "رنگ باید حروف فارسی (حداکثر ۶) باشد.", None
    if not re.fullmatch(r"[0-9]{1,6}", km):
        return False, "کارکرد باید عددی لاتین حداکثر ۶ رقمی باشد.", None

    # قیمت
    if price_raw:
        if not re.fullmatch(r"[0-9]{1,}", price_raw.replace(",", "")):
            return False, "قیمت باید با ارقام لاتین وارد شود.", None

    num = int(re.sub(r"[^0-9]", "", price_raw or "0") or "0")
    price_num = None
    price_words_str = None

    if cat == "فروش همکاری":
        if num > 0:
            if num > 100_000_000_000: num = 100_000_000_000
            price_num = num
            price_words_str = price_words(num)
    else:
        if num < 1 or num > 100_000_000_000:
            return False, "قیمت باید عددی معتبر تا سقف ۱۰۰ میلیارد تومان باشد.", None
        price_num = num
        price_words_str = price_words(num)

    form = {
        "category": cat, "car": car, "year": year, "color": color, "km": km,
        "insurance": ins, "gear": gear, "desc": desc,
        "price_num": price_num, "price_words": price_words_str,
        "username": "", "photos": [],
    }
    return True, None, form

# ---------- دریافت فرم از وب‌اپ ----------
@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data or "{}")
    except Exception:
        data = {}
    ok, err, form = validate_and_normalize(data)
    if not ok:
        await message.answer(err or "داده نامعتبر است."); return
    form["username"] = message.from_user.username or ""

    token = uuid4().hex
    PENDING[token] = {"form": form, "user_id": message.from_user.id, "admin_msgs": []}
    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": MAX_PHOTOS}

    await message.answer(
        "فرم شما ذخیره شد ✅\n"
        f"اکنون تا {MAX_PHOTOS} عکس ارسال کنید. هر زمان آماده بودید، «📣 انتشار در گروه» را بزنید.",
        reply_markup=user_finish_kb(token)
    )

# ---------- دریافت عکس ----------
@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess:
        return
    # اگر سشن خراب/ناقص بود، خودش را درست کن
    if "remain" not in sess or not isinstance(sess["remain"], int) or sess["remain"] < 0:
        sess["remain"] = MAX_PHOTOS

    if sess["remain"] <= 0:
        await message.reply("حداکثر ۵ عکس مجاز است. سپس «📣 انتشار در گروه» را بزنید.")
        return

    file_id = message.photo[-1].file_id
    token = sess["token"]
    PENDING.setdefault(token, {}).setdefault("form", {}).setdefault("photos", []).append(file_id)

    # کم‌کردن شمارنده
    sess["remain"] -= 1
    left = max(sess["remain"], 0)
    if left == 0:
        await message.reply("عکس ثبت شد. باقی‌مانده: 0\nاکنون «📣 انتشار در گروه» را بزنید.", reply_markup=user_finish_kb(token))
    else:
        await message.reply(f"عکس ثبت شد. باقی‌مانده: {left}")

# ---------- انتشار اولیه در مقصد ----------
async def publish_to_destination(bot: Bot, form: dict, *, show_price: bool, show_desc: bool):
    number, iso = next_daily_number()
    j = to_jalali(iso)
    caption = build_caption(form, number, j, show_price=show_price, show_desc=show_desc)
    photos = form.get("photos") or []

    # مقصد فعال از storage (اگر صفر بود، از .env)
    dest_id = get_active_destination() or SETTINGS.TARGET_GROUP_ID

    if photos:
        mg = MediaGroupBuilder()
        mg.add_photo(media=photos[0], caption=caption, parse_mode="HTML")
        for fid in photos[1:MAX_PHOTOS]:
            mg.add_photo(media=fid)
        msgs = await bot.send_media_group(dest_id, media=mg.build())
        first = msgs[0]
        return {"chat_id": first.chat.id, "msg_id": first.message_id, "has_photos": True, "number": number, "jdate": j}
    else:
        msg = await bot.send_message(dest_id, caption, parse_mode="HTML")
        return {"chat_id": msg.chat.id, "msg_id": msg.message_id, "has_photos": False, "number": number, "jdate": j}

async def send_review_to_admins(bot: Bot, form: dict, token: str, photos: list[str], grp: dict):
    """ارسال برای همه‌ی ادمین‌ها + ذخیره‌ی msg_id تا بعداً ببندیم."""
    recipients = list_admins()
    if not recipients and SETTINGS.OWNER_ID:
        recipients = [SETTINGS.OWNER_ID]
    if not recipients:
        return 0

    cap = admin_caption(form, grp.get("number"), grp.get("jdate"))
    ok = 0
    for admin_id in recipients:
        try:
            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=cap, parse_mode="HTML")
                for fid in photos[1:MAX_PHOTOS]:
                    mg.add_photo(media=fid)
                await bot.send_media_group(admin_id, media=mg.build())
            else:
                await bot.send_message(admin_id, cap, parse_mode="HTML")

            msg = await bot.send_message(admin_id, "ویرایش/اعمال:", reply_markup=admin_review_kb(token))
            PENDING[token]["admin_msgs"].append((msg.chat.id, msg.message_id))
            ok += 1
        except Exception:
            pass
    return ok

# پایان با دکمه
@router.callback_query(F.data.startswith("finish:"))
async def cb_finish(call: types.CallbackQuery):
    token = call.data.split(":", 1)[1]
    info = PENDING.get(token)
    if not info or info.get("user_id") != call.from_user.id:
        await call.answer("درخواست یافت نشد.", show_alert=True); return

    # پایان سشن عکس برای این کاربر
    PHOTO_WAIT.pop(call.from_user.id, None)

    form = info["form"]
    show_price = form["category"] != "فروش همکاری"
    show_desc  = False

    grp = await publish_to_destination(call.bot, form, show_price=show_price, show_desc=show_desc)
    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": (form["category"] == "فروش همکاری"), "desc": True}

    sent = await send_review_to_admins(call.bot, form, token, form.get("photos") or [], grp)

    await call.message.edit_text("📣 پست اولیه منتشر شد و برای ادمین‌ها ارسال گردید." if sent else
                                 "📣 پست اولیه منتشر شد اما ادمینی تنظیم نشده.")
    await call.answer("ارسال شد.")

# سازگاری با /done
@router.message(Command("done"))
async def on_done(message: types.Message):
    sess = PHOTO_WAIT.pop(message.from_user.id, None)
    if not sess:
        await message.reply("جلسه‌ای برای عکس فعال نیست."); return

    token = sess["token"]
    info = PENDING.get(token)
    if not info:
        await message.reply("درخواست یافت نشد."); return

    form = info["form"]
    show_price = form["category"] != "فروش همکاری"
    show_desc  = False

    grp = await publish_to_destination(message.bot, form, show_price=show_price, show_desc=show_desc)
    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": (form["category"] == "فروش همکاری"), "desc": True}

    sent = await send_review_to_admins(message.bot, form, token, form.get("photos") or [], grp)

    await message.reply("پست اولیه منتشر شد ✅ و برای ادمین ارسال گردید." if sent else
                        "پست اولیه منتشر شد ✅ اما ادمینی تنظیم/دریافت نشد.")

# ---------- ویرایش‌های ادمین ----------
@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}
    await call.message.reply("قیمت جدید را با ارقام لاتین (تومان) به صورت عدد بفرستید. سقف ۱۰۰ میلیارد.")
    await call.answer()

@router.callback_query(F.data.startswith("edit_desc:"))
async def cb_edit_desc(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
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
        ADMIN_EDIT_WAIT.pop(message.from_user.id, None)
        await message.reply("درخواست یافت نشد."); return

    form = info["form"]
    if field == "price":
        t = message.text.strip()
        if contains_persian_digits(t) or not re.fullmatch(r"[0-9]{1,}", t.replace(",", "")):
            await message.reply("قیمت نامعتبر است. فقط ارقام لاتین وارد کنید."); return
        num = int(re.sub(r"[^0-9]", "", t) or "0")
        if num < 1 or num > 100_000_000_000:
            await message.reply("قیمت نامعتبر است. (تا سقف ۱۰۰ میلیارد)"); return
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

    # بستن پیام‌های ویرایش برای همه‌ی ادمین‌ها
    for (cid, mid) in info.get("admin_msgs", []):
        try:
            await call.bot.edit_message_text("✅ اعمال شد روی پست گروه", chat_id=cid, message_id=mid)
        except Exception:
            pass

    await call.answer("اعمال شد.")
    PENDING.pop(token, None)

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    info = PENDING.pop(token, None)
    if info:
        for (cid, mid) in info.get("admin_msgs", []):
            try:
                await call.bot.edit_message_text("❌ رد شد", chat_id=cid, message_id=mid)
            except Exception:
                pass
    await call.answer("رد شد.")
