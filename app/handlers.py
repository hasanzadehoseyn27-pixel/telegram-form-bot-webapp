# app/handlers.py
import json, re
from uuid import uuid4
import jdatetime

from aiogram import Router, F, html, types, Bot
from aiogram.filters import CommandStart, Command, BaseFilter
from aiogram.utils.media_group import MediaGroupBuilder

from .config import SETTINGS
from .keyboards import (
    start_keyboard,
    admin_menu_kb,      # ریشه پنل مدیریتی
    admin_admins_kb,    # زیرمنو ادمین‌ها
    admin_allowed_kb,   # زیرمنو کانال‌های مجاز
    admin_review_kb,
    user_finish_kb,
)
from .storage import (
    next_daily_number,
    list_admins, add_admin, remove_admin, is_admin,
    is_owner,
    add_destination,  # فقط برای ثبت عنوان کانال/سازگاری
    list_allowed_channels, add_allowed_channel, remove_allowed_channel,
    is_channel_allowed,
)

router = Router()

# --- تنظیمات داخلی ---
MAX_PHOTOS = 5

# حافظه‌ی موقت
PENDING: dict[str, dict] = {}           # token -> {...}
PHOTO_WAIT: dict[int, dict] = {}        # user_id -> {token, remain}
ADMIN_EDIT_WAIT: dict[int, dict] = {}   # admin_id -> {token, field}
ADMIN_WAIT_INPUT: dict[int, dict] = {}  # admin_id -> {mode: add/remove}
ACCESS_CH_WAIT: dict[int, dict] = {}    # owner_id -> {mode: add/remove}

# ==========================
#  فیلترهای سفارشی برای جلوگیری از تداخل
# ==========================
class WaitingAdminEdit(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id in ADMIN_EDIT_WAIT

class WaitingOwnerAccess(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id in ACCESS_CH_WAIT

# ====== کمکی‌ها ======
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
        b = num // 1_000_000_000; parts.append(f"{b} میلیارد"); num %= 1_000_000_000
    if num >= 1_000_000:
        m = num // 1_000_000; parts.append(f"{m} میلیون"); num %= 1_000_000
    if num >= 1_000:
        k = num // 1_000; parts.append(f"{k} هزار"); num %= 1_000
    if num > 0:
        parts.append(f"{num}")
    return " و ".join(parts) + " تومان"

def _price_million_to_toman_str(raw: str) -> tuple[bool, int]:
    s = (raw or "").replace(" ", "").replace(",", ".").replace("\u066B", ".")
    if contains_persian_digits(s):
        return False, 0
    if not s:
        return True, 0
    if not re.fullmatch(r"\d{1,5}(\.\d)?", s):
        return False, 0
    v = float(s)
    if v * 1_000_000 > 100_000_000_000 + 1:
        return False, 0
    return True, int(round(v * 1_000_000))

def _parse_admin_price(text: str) -> tuple[bool, int]:
    s = (text or "").strip().replace(",", ".").replace("\u066B", ".")
    if contains_persian_digits(s):
        return False, 0
    if re.fullmatch(r"\d{1,5}(\.\d)?", s):
        return True, int(round(float(s) * 1_000_000))
    if re.fullmatch(r"\d{1,12}", s):
        n = int(s)
        if 1 <= n <= 100_000_000_000:
            return True, n
    return False, 0

# --- چک عضویت کاربر در کانال اصلی (.env) ---
async def _user_is_member(bot: Bot, user_id: int) -> bool:
    try:
        cm = await bot.get_chat_member(SETTINGS.TARGET_GROUP_ID, user_id)
        return str(getattr(cm, "status", "")).lower() in {"member","administrator","creator","owner"}
    except Exception:
        return False

# ====== متن پنل ادیت ادمین ======
def admin_panel_text(form: dict) -> str:
    return (
        "ویرایش/اعمال:\n"
        f"• قیمت فعلی: {html.quote(form.get('price_words') or '—')}\n"
        f"• توضیحات فعلی: {(html.quote(form.get('desc') or '—'))[:400]}\n\n"
        "یک مورد را انتخاب کنید:"
    )

async def refresh_admin_panels(bot: Bot, token: str):
    info = PENDING.get(token) or {}
    form = info.get("form") or {}
    for chat_id, msg_id in (info.get("admin_msgs") or []):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=admin_panel_text(form),
                parse_mode="HTML",
                reply_markup=admin_review_kb(token),
            )
        except Exception:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=admin_review_kb(token),
                )
            except Exception:
                pass

# ====== ساخت کپشن‌ها ======
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
    if show_desc and (form.get("desc") or "").strip():
        parts.append(f"📝 <b>توضیحات:</b>\n{html.quote(form['desc'])}")
    parts.append(f"☎️ <b>تماس:</b>\nکیوان  —  {lrm_number}")
    parts.append(f"\n🗓️ <i>{jdate}</i>")
    return "\n".join(parts)

def admin_caption(form, number, jdate, *, phone=None, username=None, include_contact=False) -> str:
    ins_text = f"{form.get('insurance')} ماه" if form.get("insurance") else "—"
    lines = []
    if include_contact:
        lines.append(f"📞 {html.quote(phone)}" if phone else "📞 —")
        uname = (username or "")
        if uname and not uname.startswith("@"): uname = "@"+uname
        lines.append(f"👤 {html.quote(uname)}" if uname else "👤 بدون نام کاربری")
        lines.append("")
    lines += [
        "🧪 <b>موارد نیازمند ویرایش/تایید:</b>",
        f"💵 <b>قیمت پیشنهادی:</b> {html.quote(form.get('price_words') or '—')}",
        f"📝 <b>توضیحات پیشنهادی:</b>\n{html.quote(form.get('desc') or '—')}",
        "—" * 10,
        "📋 <b>خلاصه آگهی</b>",
        f"دسته: {html.quote(form['category'])}",
        f"نام خودرو: {html.quote(form['car'])}",
        f"سال/رنگ/کارکرد: {html.quote(form['year'])} / {html.quote(form['color'])} / {html.quote(form['km'])}km",
        f"بیمه/گیربکس: {html.quote(ins_text)} / {html.quote(form.get('gear') or '—')}",
        f"\n🗓️ <i>{jdate}</i>  •  ⏱️ <b>#{number}</b>",
    ]
    return "\n".join(lines)

# ====== شروع ======
@router.message(CommandStart())
async def on_start(message: types.Message):
    if not SETTINGS.WEBAPP_URL:
        await message.answer("WEBAPP_URL در .env تنظیم نشده است.")
        return

    kb = start_keyboard(SETTINGS.WEBAPP_URL, is_admin(message.from_user.id))

    # اگر عضو نیست: هم لینک عضویت بده، هم همان لحظه کیبورد پایین را ست کن
    if not await _user_is_member(message.bot, message.from_user.id):
        join_kb = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="بانک خودرو", url="https://t.me/tetsbankkhodro")]]
        )
        await message.answer("برای استفاده از ربات، ابتدا عضو کانال زیر شوید:", reply_markup=join_kb)
        await message.answer("پس از عضویت، همین پایین «📝 فرم ثبت آگهی» را بزنید.", reply_markup=kb)
        return

    await message.answer("برای ثبت آگهی، دکمه زیر را بزنید:", reply_markup=kb)

# ====== پنل مدیریتی ======
@router.message(F.text == "⚙️ پنل مدیریتی")
async def open_admin_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("این بخش فقط برای ادمین‌هاست.")
        return
    kb = admin_menu_kb(is_owner(message.from_user.id))
    await message.answer("پنل مدیریتی:\nیک گزینه را انتخاب کنید:", reply_markup=kb)

@router.message(F.text == "👤 مدیریت ادمین‌ها")
async def open_admins_submenu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید."); return
    await message.answer("مدیریت ادمین‌ها:", reply_markup=admin_admins_kb())

@router.message(F.text == "📡 مدیریت کانال‌های مجاز")
async def open_allowed_submenu(message: types.Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ این بخش فقط برای مدیر اصلی است."); return
    await message.answer("مدیریت کانال‌های مجاز:", reply_markup=admin_allowed_kb())

@router.message(F.text == "🔙 بازگشت به پنل")
async def back_to_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید."); return
    await message.answer("بازگشت به پنل مدیریتی.", reply_markup=admin_menu_kb(is_owner(message.from_user.id)))

@router.message(F.text == "🔙 بازگشت")
async def admin_back_to_main(message: types.Message):
    kb = start_keyboard(SETTINGS.WEBAPP_URL, is_admin(message.from_user.id))
    await message.answer("بازگشت به منوی اصلی.", reply_markup=kb)

# ====== مدیریت ادمین‌ها ======
@router.message(F.text == "📋 لیست ادمین‌ها")
async def admin_list_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    admins = list_admins()
    txt = "ادمین‌های فعلی:\n" + ("\n".join(map(str, admins)) if admins else "— خالی —")
    await message.answer(txt)

@router.message(F.text == "➕ افزودن ادمین")
async def admin_add_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "add"}
    await message.answer("آیدی عددی کاربر را ارسال کنید تا ادمین شود:")

@router.message(F.text == "🗑 حذف ادمین")
async def admin_remove_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    ADMIN_WAIT_INPUT[message.from_user.id] = {"mode": "remove"}
    await message.answer("آیدی عددی ادمین را ارسال کنید تا حذف شود:")

@router.message(F.text.regexp(r"^\d{4,}$"))
async def admin_id_input(message: types.Message):
    w = ADMIN_WAIT_INPUT.get(message.from_user.id)
    if not w or not is_admin(message.from_user.id): return
    uid = int(message.text.strip()); mode = w["mode"]
    if mode == "add":
        ok = add_admin(uid); await message.reply("✅ اضافه شد." if ok else "ℹ️ قبلاً ادمین بوده.")
    elif mode == "remove":
        ok = remove_admin(uid); await message.reply("🗑 حذف شد." if ok else "⚠️ امکان حذف نیست/یافت نشد.")
    ADMIN_WAIT_INPUT.pop(message.from_user.id, None)

# ====== اعتبارسنجی و دریافت فرم ======
def validate_and_normalize(payload: dict) -> tuple[bool, str | None, dict | None]:
    cat = (payload.get("category") or "").strip()
    car = (payload.get("car") or "").strip()
    year = (payload.get("year") or "").strip()
    color = (payload.get("color") or "").strip()
    km = (payload.get("km") or "").strip()
    price_raw = (payload.get("price") or "").strip()
    ins = (payload.get("insurance") or "").strip()
    gear = (payload.get("gear") or "").strip()
    desc = (payload.get("desc") or "").strip()
    phone = (payload.get("phone") or "").strip()

    if (contains_persian_digits(car) or contains_persian_digits(year) or
        contains_persian_digits(km) or contains_persian_digits(ins) or
        contains_persian_digits(phone)):
        return False, "لطفاً اعداد را فقط با رقم‌های لاتین (0-9) وارد کنید.", None

    if not car or len(car) > 10 or re.search(r"\d{5,}", car): return False, "نام خودرو نامعتبر است.", None
    if not re.fullmatch(r"[0-9]{4}", year): return False, "سال ساخت باید ۴ رقم لاتین باشد.", None
    if not re.fullmatch(r"[آ-ی\s]{1,6}", color): return False, "رنگ باید حروف فارسی (حداکثر ۶) باشد.", None
    if not re.fullmatch(r"[0-9]{1,6}", km): return False, "کارکرد باید عددی لاتین حداکثر ۶ رقمی باشد.", None
    if ins and not re.fullmatch(r"[0-9]{1,2}", ins): return False, "مهلت بیمه حداکثر ۲ رقم لاتین (ماه) باشد.", None
    if not re.fullmatch(r"09\d{9}", phone): return False, "شماره تماس باید ۱۱ رقم و با فرمت 09xxxxxxxxx باشد.", None

    ok_num, toman = _price_million_to_toman_str(price_raw)
    if not ok_num: return False, "قیمت را با ارقام لاتین و به صورت «میلیون تومان» وارد کنید (مثلاً 50.5).", None

    price_num = None; price_words_str = None
    if cat == "فروش همکاری":
        if toman > 0: price_num = toman; price_words_str = price_words(toman)
    else:
        if toman < 1: return False, "قیمت لازم است (به میلیون تومان).", None
        price_num = toman; price_words_str = price_words(toman)

    form = {
        "category": cat, "car": car, "year": year, "color": color, "km": km,
        "insurance": ins, "gear": gear, "desc": desc,
        "price_num": price_num, "price_words": price_words_str,
        "phone": phone, "username": "", "photos": [],
    }
    return True, None, form

@router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    # اگر عضو نبود، همین‌جا جلوی ثبت را می‌گیریم (بدون نیاز به /start)
    if not await _user_is_member(message.bot, message.from_user.id):
        join_kb = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="بانک خودرو", url="https://t.me/tetsbankkhodro")]]
        )
        await message.answer("⛔ ابتدا عضو کانال شوید. بعد از عضویت، از دکمهٔ پایین «📝 فرم ثبت آگهی» استفاده کنید.", reply_markup=join_kb)
        return

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
        "فرم شما ذخیره شد ✅\nاکنون تا ۵ عکس ارسال کنید. هر زمان آماده بودید، «📣 انتشار در گروه» را بزنید.",
        reply_markup=user_finish_kb(token),
    )

# ====== عکس ======
@router.message(F.photo)
async def on_photo(message: types.Message):
    # جلوگیری از ادامهٔ کار اگر عضو نیست
    if not await _user_is_member(message.bot, message.from_user.id):
        await message.reply("⛔ ابتدا عضو کانال شوید و دوباره تلاش کنید.")
        return

    sess = PHOTO_WAIT.get(message.from_user.id)
    if not sess: return
    if "remain" not in sess or not isinstance(sess["remain"], int) or sess["remain"] < 0: sess["remain"] = MAX_PHOTOS
    if sess["remain"] <= 0:
        await message.reply("حداکثر ۵ عکس مجاز است. سپس «📣 انتشار در گروه» را بزنید.", reply_markup=user_finish_kb(sess["token"])); return

    file_id = message.photo[-1].file_id
    token = sess["token"]
    PENDING.setdefault(token, {}).setdefault("form", {}).setdefault("photos", []).append(file_id)
    sess["remain"] -= 1; left = max(sess["remain"], 0)

    await message.reply(
        f"عکس ثبت شد. باقی‌مانده: {left}",
        reply_markup=user_finish_kb(token),
    )

# ====== انتشار اولیه ======
async def publish_to_destination(bot: Bot, form: dict, *, show_price: bool, show_desc: bool):
    number, iso = next_daily_number()
    j = to_jalali(iso)
    caption = build_caption(form, number, j, show_price=show_price, show_desc=show_desc)
    photos = form.get("photos") or []
    dest_id = SETTINGS.TARGET_GROUP_ID

    if photos:
        mg = MediaGroupBuilder()
        mg.add_photo(media=photos[0], caption=caption, parse_mode="HTML")
        for fid in photos[1:MAX_PHOTOS]: mg.add_photo(media=fid)
        msgs = await bot.send_media_group(dest_id, media=mg.build())
        first = msgs[0]
        return {"chat_id": first.chat.id, "msg_id": first.message_id, "has_photos": True, "number": number, "jdate": j}
    else:
        msg = await bot.send_message(dest_id, caption, parse_mode="HTML")
        return {"chat_id": msg.chat.id, "msg_id": msg.message_id, "has_photos": False, "number": number, "jdate": j}

# پنل بررسی به ادمین‌ها
async def send_review_to_admins(bot: Bot, form: dict, token: str, photos: list[str], grp: dict):
    recipients = list_admins()
    if not recipients: return 0
    ok = 0
    for admin_id in recipients:
        try:
            include_contact = is_owner(admin_id)
            cap = admin_caption(form, grp.get("number"), grp.get("jdate"),
                                phone=form.get("phone"), username=form.get("username"),
                                include_contact=include_contact)
            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=cap, parse_mode="HTML")
                for fid in photos[1:MAX_PHOTOS]: mg.add_photo(media=fid)
                await bot.send_media_group(admin_id, media=mg.build())
            else:
                await bot.send_message(admin_id, cap, parse_mode="HTML")

            panel_msg = await bot.send_message(admin_id, admin_panel_text(form), parse_mode="HTML", reply_markup=admin_review_kb(token))
            PENDING[token].setdefault("admin_msgs", []).append((panel_msg.chat.id, panel_msg.message_id))
            ok += 1
        except Exception:
            pass
    return ok

# ====== دکمه «انتشار در گروه» ======
@router.callback_query(F.data.startswith("finish:"))
async def cb_finish(call: types.CallbackQuery):
    # اگر عضو نیست → اجازهٔ انتشار اولیه نده
    if not await _user_is_member(call.bot, call.from_user.id):
        await call.answer("⛔ ابتدا عضو کانال شوید.", show_alert=True)
        return

    token = call.data.split(":", 1)[1]
    data = PENDING.get(token)
    if not data or data.get("user_id") != call.from_user.id:
        await call.answer("جلسه یافت نشد.", show_alert=True); return

    if not is_channel_allowed(SETTINGS.TARGET_GROUP_ID):
        await call.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.\nبرای فعال‌سازی دسترسی، با مدیر اصلی هماهنگ کنید.", show_alert=True)
        return

    form = data["form"]
    show_price = form["category"] != "فروش همکاری"
    show_desc = False
    grp = await publish_to_destination(call.bot, form, show_price=show_price, show_desc=show_desc)

    PENDING[token]["grp"] = grp
    PENDING[token]["needs"] = {"price": (form["category"] == "فروش همکاری"), "desc": True}

    sent = await send_review_to_admins(call.bot, form, token, form.get("photos") or [], grp)
    PHOTO_WAIT.pop(call.from_user.id, None)

    await call.answer()
    try:
        await call.message.edit_text("ثبت شد ✅\nپست اولیه در گروه منتشر شد" + (" و برای ادمین‌ها ارسال گردید." if sent else " اما ادمینی دریافت نکرد."))
    except Exception:
        pass
    await call.message.answer("پست اولیه منتشر شد ✅ و برای بررسی به ادمین‌ها ارسال گردید.")

# ====== ویرایش‌ها ======
@router.callback_query(F.data.startswith("edit_price:"))
async def cb_edit_price(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): 
        await call.answer("شما ادمین نیستید.", show_alert=True); 
        return
    token = call.data.split(":", 1)[1]
    if token not in PENDING: 
        await call.answer("درخواست یافت نشد/جلسه منقضی شده.", show_alert=True); 
        return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "price"}
    await call.answer("قیمت جدید را بفرستید…")
    await call.message.reply("قیمت جدید را با ارقام لاتین بفرستید (میلیون با اعشار یک‌رقمی مثل 50.5 یا تومانِ خالی). سقف ۱۰۰ میلیارد.")

@router.callback_query(F.data.startswith("edit_desc:"))
async def cb_edit_desc(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): 
        await call.answer("شما ادمین نیستید.", show_alert=True); 
        return
    token = call.data.split(":", 1)[1]
    if token not in PENDING: 
        await call.answer("درخواست یافت نشد/جلسه منقضی شده.", show_alert=True); 
        return
    ADMIN_EDIT_WAIT[call.from_user.id] = {"token": token, "field": "desc"}
    await call.answer("توضیحات جدید را بفرستید…")
    await call.message.reply("توضیحات جدید را بفرستید.")

# --- هندلر متخصّص برای ویرایش (تا با F.text های دیگر تداخل نکند)
@router.message(WaitingAdminEdit())
async def on_admin_text_edit(message: types.Message):
    w = ADMIN_EDIT_WAIT.get(message.from_user.id)
    if not w: 
        return
    token, field = w["token"], w["field"]
    info = PENDING.get(token)
    if not info:
        ADMIN_EDIT_WAIT.pop(message.from_user.id, None)
        await message.reply("درخواست یافت نشد/جلسه منقضی شده."); 
        return

    form = info["form"]
    if field == "price":
        ok, n_toman = _parse_admin_price(message.text)
        if not ok: 
            await message.reply("عدد نامعتبر. فقط ارقام لاتین؛ میلیون با اعشار یک‌رقمی (مثل 50.5) یا تومان خالی.")
            return
        form["price_num"] = n_toman
        form["price_words"] = price_words(n_toman)
        await message.reply(f"قیمت به «{form['price_words']}» تغییر کرد.")
    elif field == "desc":
        form["desc"] = message.text.strip()
        await message.reply("توضیحات به‌روزرسانی شد.")

    ADMIN_EDIT_WAIT.pop(message.from_user.id, None)
    await message.answer(
        admin_panel_text(form),
        parse_mode="HTML",
        reply_markup=admin_review_kb(token),
    )
    await refresh_admin_panels(message.bot, token)

# --- جریان متنِ مدیریت کانال‌های مجاز فقط وقتی OWNER در حالت مخصوص است
@router.message(WaitingOwnerAccess())
async def access_channel_flow(message: types.Message):
    if not is_owner(message.from_user.id):
        ACCESS_CH_WAIT.pop(message.from_user.id, None)
        await message.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.\nبرای فعال‌سازی دسترسی، با مدیر اصلی هماهنگ کنید.")
        return

    st = ACCESS_CH_WAIT.get(message.from_user.id)
    if not st:
        return

    # تنها لینک‌های عمومی t.me/username
    t = (message.text or "").strip()
    m = re.search(r"(?:https?://)?t\.me/([^ \n]+)", t)
    if not m:
        await message.reply("❗ فقط لینک عمومی t.me/username پشتیبانی می‌شود.\nاگر کانال خصوصی است یا لینک joinchat/+ دارد، ابتدا به کانال یوزرنیم عمومی بدهید.")
        return
    slug = m.group(1).split("?")[0].strip()
    if slug.startswith("+") or slug.startswith("joinchat/") or slug.startswith("c/"):
        await message.reply("❗ فقط کانال/گروه با یوزرنیم عمومی پشتیبانی می‌شود."); return
    if not re.fullmatch(r"[A-Za-z0-9_]{5,}", slug):
        await message.reply("❗ یوزرنیم نامعتبر است."); return
    ref = slug if slug.startswith("@") else ("@" + slug)

    try:
        chat = await message.bot.get_chat(ref)
        cid = chat.id
        title = getattr(chat, "title", "") or getattr(chat, "full_name", "") or ""
    except Exception:
        await message.reply("❌ نتوانستم اطلاعات این لینک را بگیرم. مطمئن شوید ربات داخل کانال/گروه عضو است و یوزرنیم عمومی دارد.")
        return

    mode = st.get("mode")
    if mode == "add":
        ok = add_allowed_channel(cid)
        if ok:
            add_destination(cid, title)
            await message.reply(f"✅ کانال مجاز اضافه شد.\nchat_id: {cid}\nعنوان: {title or ref}")
        else:
            await message.reply("ℹ️ این کانال/گروه قبلاً در لیست مجاز بود.")
    elif mode == "remove":
        if int(cid) == int(SETTINGS.TARGET_GROUP_ID):
            await message.reply("⛔ امکان حذف «کانال اصلی (.env)» وجود ندارد.")
        else:
            ok = remove_allowed_channel(cid)
            await message.reply("🗑 حذف شد." if ok else "ℹ️ چنین کانالی در لیست نبود.")
    else:
        await message.reply("وضعیت ناشناخته.")
    ACCESS_CH_WAIT.pop(message.from_user.id, None)

# ====== اعمال نهایی ======
@router.callback_query(F.data.startswith("publish:"))
async def cb_publish(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    info = PENDING.get(token)
    if not info: await call.answer("درخواست یافت نشد.", show_alert=True); return

    if not is_channel_allowed(SETTINGS.TARGET_GROUP_ID):
        await call.answer("⛔ شما در حال حاضر به این بخش دسترسی ندارید.\nبرای فعال‌سازی دسترسی، با مدیر اصلی هماهنگ کنید.", show_alert=True)
        return

    form  = info["form"]
    grp   = info.get("grp") or {}
    needs = info.get("needs") or {"price": False, "desc": True}

    number = grp.get("number"); jdate = grp.get("jdate")
    if not number or not jdate:
        n, iso = next_daily_number(); number, jdate = n, to_jalali(iso)

    show_price = not needs.get("price", False) or bool(form.get("price_words"))
    show_desc  = not needs.get("desc", False)  or bool(form.get("desc"))
    caption    = build_caption(form, number, jdate, show_price=show_price, show_desc=show_desc)
    photos     = form.get("photos") or []

    # تلاش برای ادیت؛ در صورت خطا، ارسال جدید (fallback)
    edited = False
    if grp.get("chat_id") and grp.get("msg_id"):
        try:
            if grp.get("has_photos"):
                await call.bot.edit_message_caption(chat_id=grp["chat_id"], message_id=grp["msg_id"], caption=caption, parse_mode="HTML")
            else:
                await call.bot.edit_message_text(chat_id=grp["chat_id"], message_id=grp["msg_id"], text=caption, parse_mode="HTML")
            edited = True
        except Exception:
            edited = False

    if not edited:
        try:
            if photos:
                mg = MediaGroupBuilder()
                mg.add_photo(media=photos[0], caption=caption, parse_mode="HTML")
                for fid in photos[1:MAX_PHOTOS]: mg.add_photo(media=fid)
                await call.bot.send_media_group(SETTINGS.TARGET_GROUP_ID, media=mg.build())
            else:
                await call.bot.send_message(SETTINGS.TARGET_GROUP_ID, caption, parse_mode="HTML")
        except Exception:
            await call.answer("خطا در ارسال/ادیت پست.", show_alert=True); return

    for chat_id, msg_id in (info.get("admin_msgs") or []):
        try:
            await call.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
            await call.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="✅ اعمال شد روی پست گروه")
        except Exception:
            pass

    await call.answer("اعمال شد.")
    await call.message.answer("✅ اعمال شد روی پست گروه")
    try: await call.message.edit_text("✅ اعمال شد روی پست گروه")
    except Exception: pass

    PENDING.pop(token, None)

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    info = PENDING.pop(token, None)
    await call.answer("رد شد.")
    if info:
        for chat_id, msg_id in (info.get("admin_msgs") or []):
            try:
                await call.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
                await call.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="❌ رد شد")
            except Exception:
                pass
    try: await call.message.edit_text("❌ رد شد")
    except Exception: pass
