import json, re, asyncio
from uuid import uuid4
import jdatetime

from aiogram import Router, F, html, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils.media_group import MediaGroupBuilder

from .config import SETTINGS
from .keyboards import start_keyboard, admin_menu_kb, admin_review_kb, publish_button
from .storage import (
    next_daily_number, list_admins, add_admin, remove_admin, is_admin,
    list_dests, get_active_dest, set_active_dest, add_dest, remove_dest
)

router = Router()

# حافظهٔ موقت
PENDING: dict[str, dict] = {}           # token -> {form, user_id, grp:{...}, needs:{price,desc}, admin_btn_msgs:[{chat_id,msg_id}]}
PHOTO_WAIT: dict[int, dict] = {}        # user_id -> {token, remain}
ADMIN_EDIT_WAIT: dict[int, dict] = {}   # admin_id -> {token, field}
ADMIN_WAIT_INPUT: dict[int, dict] = {}  # admin_id -> {mode: add/remove/dest_add/dest_set/dest_remove}

def to_jalali(date_iso: str) -> str:
    y, m, d = map(int, date_iso.split("-"))
    j = jdatetime.date.fromgregorian(year=y, month=m, day=d)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"

def has_persian_digits(s: str) -> bool:
    return bool(re.search(r'[\u06F0-\u06F9\u0660-\u0669]', s or ""))

def price_words(num_toman: int) -> str:
    if num_toman >= 100_000_000_000:
        num_toman = 100_000_000_000
    n = num_toman
    parts = []
    if n >= 1_000_000_000:
        b = n // 1_000_000_000; parts.append(f"{b} میلیارد"); n %= 1_000_000_000
    if n >= 1_000_000:
        m = n // 1_000_000; parts.append(f"{m} میلیون"); n %= 1_000_000
    if n >= 1_000:
        k = n // 1_000; parts.append(f"{k} هزار"); n %= 1_000
    if n > 0:
        parts.append(f"{n}")
    return " و ".join(parts) + " تومان"

def build_caption(form: dict, number: int, jdate: str, *, show_price: bool, show_desc: bool) -> str:
    # سطر اول: شماره آگهی
    parts = [f"🔷 <b>شماره آگهی #{number}</b>", "🚗 <b>آگهی جدید</b>"]
    parts += [
        f"🏷️ <b>نام خودرو:</b> {html.quote(form['car'])}",
        f"📅 <b>سال ساخت:</b> {html.quote(form['year'])}",
        f"🎨 <b>رنگ:</b> {html.quote(form['color'])}",
        f"⚙️ <b>گیربکس:</b> {html.quote(form.get('gear') or '—')}",
        f"🛡️ <b>مهلت بیمه:</b> {html.quote(form.get('insurance') or '—')}",
        f"📈 <b>کارکرد:</b> {html.quote(form['km'])} کیلومتر",
    ]
    if show_price and form.get("price_words"):
        parts.append(f"💵 <b>قیمت:</b> {html.quote(form['price_words'])}")
    if show_desc and (form.get("desc") or "").strip():
        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")
    parts.append("📞 شماره تماس: 09127475355 - کیوان")
    parts.append(f"\n🗓️ <i>{jdate}</i>")
    return "\n".join(parts)

def admin_caption(form: dict, number: int, jdate: str) -> str:
    lines = ["🧪 <b>موارد نیازمند ویرایش/تایید:</b>"]
    # هر دو فیلد برای ادمین نمایش داده شود
    lines.append(f"💵 <b>قیمت پیشنهادی:</b> {html.quote(form.get('price_words') or '—')}")
    lines.append(f"📝 <b>توضیحات پیشنهادی:</b>\n{html.quote(form.get('desc') or '—')}")
    lines.append("—" * 10)
    lines.append("📋 <b>خلاصه آگهی</b>")
    lines.append(f"دسته: {html.quote(form['category'])}")
    lines.append(f"نام خودرو: {html.quote(form['car'])}")
    lines.append(f"سال/رنگ/کارکرد: {html.quote(form['year'])} / {html.quote(form['color'])} / {html.quote(form['km'])}km")
    lines.append(f"\n🗓️ <i>{jdate}</i>")
    return "\n".join(lines)

# ---------- شروع و منو ----------
@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است."); return
    try:
        await message.answer("↻ به‌روزرسانی منو…", reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass
    kb = start_keyboard(SETTINGS.WEBAPP_URL, is_admin(message.from_user.id))
    await message.answer("برای ثبت آگهی، دکمه زیر را بزنید:", reply_markup=kb)

@router.message(Command("menu"))
async def menu(message: types.Message):
    kb = start_keyboard(SETTINGS.WEBAPP_URL, is_admin(message.from_user.id))
    await message.answer("منو به‌روزرسانی شد.", reply_markup=kb)

@router.message(F.text == "⚙️ پنل مدیریتی")
async def open_admin_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("این بخش فقط برای ادمین‌هاست."); return
    await message.answer("پنل مدیریتی:", reply_markup=None)
    await message.answer("یک گزینه را انتخاب کنید:", reply_markup=admin_menu_kb())

# ---------- مدیریت ادمین ----------
@router.callback_query(F.data == "admin:list")
async def admin_list_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    admins = list_admins()
    txt = "ادمین‌های فعلی:\n" + ("\n".join(map(str, admins)) if admins else "— خالی —")
    await call.message.answer(txt); await call.answer()

@router.callback_query(F.data == "admin:add")
async def admin_add_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "add"}
    await call.message.answer("آیدی عددی کاربر را ارسال کنید تا ادمین شود:"); await call.answer()

@router.callback_query(F.data == "admin:remove")
async def admin_remove_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "remove"}
    await call.message.answer("آیدی عددی ادمین را ارسال کنید تا حذف شود (OWNER حذف نمی‌شود):"); await call.answer()

# ---------- مدیریت مقاصد انتشار ----------
@router.callback_query(F.data == "dest:list")
async def dest_list_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    active = get_active_dest()
    items = list_dests()
    if not items:
        await call.message.answer("مقصدی ثبت نشده است."); await call.answer(); return
    lines = ["📦 مقاصد:"]
    for it in items:
        mark = "✅" if int(it["id"]) == int(active) else "•"
        title = it.get("title") or "—"
        lines.append(f"{mark} {it['id']}  —  {title}")
    await call.message.answer("\n".join(lines)); await call.answer()

@router.callback_query(F.data == "dest:active")
async def dest_active_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    active = get_active_dest()
    items = list_dests()
    title = ""
    for it in items:
        if int(it["id"]) == int(active):
            title = it.get("title") or ""
            break
    await call.message.answer(f"🎯 مقصد فعال: {active or '—'}  {('— '+title) if title else ''}")
    await call.answer()

@router.callback_query(F.data == "dest:add")
async def dest_add_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "dest_add"}
    await call.message.answer("Chat ID مقصد را بفرستید (گروه/کانال). ربات باید عضو/ادمین آن باشد."); await call.answer()

@router.callback_query(F.data == "dest:set")
async def dest_set_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "dest_set"}
    await call.message.answer("Chat ID مقصدی که باید فعال شود را ارسال کنید:"); await call.answer()

@router.callback_query(F.data == "dest:remove")
async def dest_remove_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True); return
    ADMIN_WAIT_INPUT[call.from_user.id] = {"mode": "dest_remove"}
    await call.message.answer("Chat ID مقصدی که باید حذف شود را ارسال کنید:"); await call.answer()

@router.message(F.text.regexp(r"^-?[0-9]{6,}$"))
async def on_numeric_admin_inputs(message: types.Message):
    """دریافت ورودی‌های عددی برای مودهای مدیریت/ادمین."""
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w or not is_admin(message.from_user.id):
        return
    mode = w["mode"]
    val = int(message.text.strip())

    if mode == "add":
        ok = add_admin(val)
        await message.reply("✅ اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")
    elif mode == "remove":
        ok = remove_admin(val)
        await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف نیست/یافت نشد.")
    elif mode == "dest_add":
        # تلاش برای گرفتن عنوان چت
        title = ""
        try:
            chat = await message.bot.get_chat(val)
            title = getattr(chat, "title", "") or getattr(chat, "full_name", "") or ""
        except Exception:
            title = ""
        ok = add_dest(val, title=title)
        await message.reply("✅ مقصد اضافه شد." if ok else "ℹ️ قبلاً ثبت شده بود.")
    elif mode == "dest_set":
        ok = set_active_dest(val)
        await message.reply("🎯 مقصد فعال شد." if ok else "⚠️ مقصد یافت نشد.")
    elif mode == "dest_remove":
        ok = remove_dest(val)
        await message.reply("🗑 مقصد حذف شد." if ok else "⚠️ مقصد یافت نشد.")
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
    price_raw = (payload.get("price") or "").strip()  # برحسب "میلیون تومان"
    ins   = (payload.get("insurance") or "").strip()
    gear  = (payload.get("gear") or "").strip()
    desc  = (payload.get("desc") or "").strip()

    # اعداد باید 0-9 لاتین باشند؛ ورود اعداد فارسی ممنوع
    if has_persian_digits(year) or has_persian_digits(km) or has_persian_digits(price_raw):
        return False, "اعداد باید با ارقام لاتین 0-9 وارد شوند.", None

    if not car or len(car) > 10 or re.search(r"[0-9]{5,}", car):  # فقط لاتین
        return False, "نام خودرو نامعتبر است.", None
    if not re.fullmatch(r"[0-9]{4}", year):
        return False, "سال ساخت باید ۴ رقم لاتین باشد.", None
    if not re.fullmatch(r"[آ-ی\s]{1,6}", color):
        return False, "रنگ باید حروف فارسی (حداکثر ۶) باشد.", None
    if not re.fullmatch(r"[0-9]{1,6}", km):
        return False, "کارکرد باید عددی (لاتین) حداکثر ۶ رقمی باشد.", None

    # قیمت: ورودی وب‌اپ «میلیون تومان» است => به تومان تبدیل کنیم
    price_num_toman = None
    price_words_str = None
    if cat == "فروش همکاری":
        if price_raw and re.fullmatch(r"[0-9]{1,5}", price_raw):
            price_num_toman = int(price_raw) * 1_000_000
            price_words_str = price_words(price_num_toman)
    else:
        if not re.fullmatch(r"[0-9]{1,5}", price_raw or ""):
            return False, "قیمت تا سقف ۵ رقم (میلیون تومان) و با اعداد لاتین.", None
        price_num_toman = int(price_raw) * 1_000_000
        price_words_str = price_words(price_num_toman)

    form = {
        "category": cat, "car": car, "year": year, "color": color, "km": km,
        "insurance": ins, "gear": gear, "desc": desc,
        "price_num": price_num_toman, "price_words": price_words_str,
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
    PENDING[token] = {"form": form, "user_id": message.from_user.id}
    PHOTO_WAIT[message.from_user.id] = {"token": token, "remain": 5}

    await message.answer(
        "فرم شما ذخیره شد ✅\nاگر عکس دارید ارسال کنید. در پایان روی «انتشار در گروه» بزنید.",
        reply_markup=publish_button(token)
    )

# ---------- دریافت عکس ----------
@router.message(F.photo)
async def on_photo(message: types.Message):
    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess:
        return
    if sess["remain"] <= 0:
        await message.reply("حداکثر ۵ عکس مجاز است.", reply_markup=publish_button(sess["token"]))
        return
    file_id = message.photo[-1].file_id
    token = sess["token"]
    PENDING[token]["form"]["photos"].append(file_id)
    sess["remain"] -= 1
    await message.reply(f"عکس ثبت شد. باقی‌مانده: {sess['remain']}", reply_markup=publish_button(token))

# ---------- انتشار اولیه در مقصد فعال ----------
async def publish_to_group(message: types.Message, form: dict, *, show_price: bool, show_desc: bool):
    number, iso = next_daily_number()
    j = to_jalali(iso)
    caption = build_caption(form, number, j, show_price=show_price, show_desc=show_desc)
    photos = form.get("photos") or []

    target = get_active_dest() or SETTINGS.TARGET_GROUP_ID
    if not target:
        raise RuntimeError("هیچ مقصد فعالی تنظیم نشده است.")

    if photos:
        mg = MediaGroupBuilder()
        mg.add_photo(media=photos[0], caption=caption, parse_mode="HTML")
        for fid in photos[1:5]:
            mg.add_photo(media=fid)
        msgs = await message.bot.send_media_group(target, media=mg.build())
        first = msgs[0]
        return {"chat_id": first.chat.id, "msg_id": first.message_id, "has_photos": True, "number": number, "jdate": j}
    else:
        msg = await message.bot.send_message(target, caption, parse_mode="HTML")
        return {"chat_id": msg.chat.id, "msg_id": msg.message_id, "has_photos": False, "number": number, "jdate": j}

async def send_review_to_admins(bot: Bot, form: dict, token: str, photos: list[str], grp: dict):
    """پیام بررسی برای ادمین‌ها + ذخیرهٔ پیام‌های دکمه‌دار جهت حذف بعد از تأیید."""
    recipients = list_admins()
    if not recipients and SETTINGS.OWNER_ID:
        recipients = [SETTINGS.OWNER_ID]
    if not recipients:
        return []

    cap = admin_caption(form, grp.get("number"), grp.get("jdate"))
    out = []
    for admin_id in recipients:
        try:
            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=cap, parse_mode="HTML")
                for fid in photos[1:5]:
                    mg.add_photo(media=fid)
                await bot.send_media_group(admin_id, media=mg.build())
            else:
                await bot.send_message(admin_id, cap, parse_mode="HTML")
            kb_msg = await bot.send_message(admin_id, "ویرایش/اعمال:", reply_markup=admin_review_kb(token))
            out.append({"chat_id": kb_msg.chat.id, "msg_id": kb_msg.message_id})
        except Exception:
            pass
    return out

async def _finalize_publish(message: types.Message, token: str):
    data = PENDING.get(token)
    if not data:
        await message.answer("درخواست یافت نشد."); return

    form = data["form"]
    # انتشار اولیه: توضیحات همیشه مخفی؛ قیمت فقط در «فروش همکاری» مخفی
    show_price = form["category"] != "فروش همکاری"
    show_desc  = False
    grp = await publish_to_group(message, form, show_price=show_price, show_desc=show_desc)

    # نگهداری اطلاعات جهت ادیت
    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": (form["category"] == "فروش همکاری"), "desc": True}

    # ارسال برای ادمین‌ها و ذخیرهٔ پیام‌های دکمه‌دار جهت حذف بعد از تأیید
    admin_msgs = await send_review_to_admins(message.bot, form, token, form.get("photos") or [], grp)
    PENDING[token]["admin_btn_msgs"] = admin_msgs

    await message.answer("پست اولیه منتشر شد ✅" + ("" if admin_msgs else "\n(هشدارد: ادمینی برای بررسی ثبت نیست)"))

@router.message(Command("done"))
async def on_done(message: types.Message):
    sess = PHOTO_WAIT.pop(message.from_user.id, None)
    if not sess:
        await message.reply("جلسه‌ای برای عکس فعال نیست."); return
    await _finalize_publish(message, sess["token"])

@router.callback_query(F.data.startswith("userdone:"))
async def cb_user_done(call: types.CallbackQuery):
    token = call.data.split(":", 1)[1]
    # اگر جلسه عکس باز بود، ببند
    _ = PHOTO_WAIT.pop(call.from_user.id, None)
    await _finalize_publish(call.message, token)
    try:
        await call.answer("منتشر شد.")
    except Exception:
        pass

# ---------- ویرایش‌های ادمین ----------
@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    if token not in PENDING:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}
    await call.message.reply("قیمت جدید را به صورت «میلیون تومان» فقط با اعداد لاتین (حداکثر ۵ رقم) ارسال کنید.")
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
        t = (message.text or "").strip()
        # فقط 0-9 لاتین؛ بدون تومان؛ حداکثر ۵ رقم
        if has_persian_digits(t) or not re.fullmatch(r"[0-9]{1,5}", t):
            await message.reply("فقط عدد لاتین 0-9، حداکثر ۵ رقم (واحد: میلیون تومان).")
            return
        num_toman = int(t) * 1_000_000
        if num_toman < 1 or num_toman > 100_000_000_000:
            await message.reply("عدد نامعتبر (حداکثر ۱۰۰ میلیارد تومان).")
            return
        form["price_num"] = num_toman
        form["price_words"] = price_words(num_toman)
        await message.reply(f"قیمت به «{form['price_words']}» تغییر کرد.")
    elif field == "desc":
        form["desc"] = (message.text or "").strip()
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

    # تک‌تأیید: پیام‌های دکمه‌دار برای بقیه را پاک کن
    for ref in info.get("admin_btn_msgs") or []:
        try:
            await call.bot.delete_message(chat_id=ref["chat_id"], message_id=ref["msg_id"])
        except Exception:
            pass

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
    info = PENDING.pop(token, None)
    # پاکسازی پیام‌های دکمه‌دار
    if info:
        for ref in info.get("admin_btn_msgs") or []:
            try:
                await call.bot.delete_message(chat_id=ref["chat_id"], message_id=ref["msg_id"])
            except Exception:
                pass
    await call.answer("رد شد.")
    try:
        await call.message.edit_text(call.message.text + "\n\n❌ رد شد")
    except Exception:
        pass
