cat > main.py <<'PY'
import asyncio, os, json
from uuid import uuid4

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F, html, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from aiogram.client.session.aiohttp import AiohttpSession  # proxy (optional)

# -------- env --------
load_dotenv()
BOT_TOKEN       = (os.getenv("BOT_TOKEN") or "").strip()
ADMIN_IDS       = {int(x) for x in (os.getenv("ADMIN_IDS") or "").replace(" ", "").split(",") if x}
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID", "0"))
PROXY_URL       = (os.getenv("PROXY_URL") or "").strip()
WEBAPP_URL      = (os.getenv("WEBAPP_URL") or "").strip()

session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
bot = Bot(BOT_TOKEN, session=session)

dp, router = Dispatcher(), Router()
dp.include_router(router)

class Form(StatesGroup):
    name = State()

PENDING: dict[str, dict] = {}

async def process_name_submission(user: types.User, name: str, reply_to: types.Message):
    name = (name or "").strip()
    if not name:
        await reply_to.answer("نام خالی است. دوباره تلاش کنید.")
        return
    await reply_to.answer("فرم شما برای ادمین ارسال شد ✅")
    token = uuid4().hex
    PENDING[token] = {"user_id": user.id, "name": name}

    caption = (
        "🆕 فرم جدید\n"
        f"نام: {html.quote(name)}\n"
        f"از کاربر: {html.quote(user.full_name)} (id={user.id})"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید", callback_data=f"approve:{token}"),
        InlineKeyboardButton(text="❌ رد",   callback_data=f"reject:{token}")
    ]])
    for admin_id in ADMIN_IDS:
        try: await bot.send_message(admin_id, caption, reply_markup=kb)
        except Exception: pass

row = [KeyboardButton(text="📝 فرم ساده")]
if WEBAPP_URL:
    row.append(KeyboardButton(text="🌐 فرم زیبا", web_app=WebAppInfo(url=WEBAPP_URL)))
start_kb = ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

@router.message(CommandStart())
async def on_start(message: types.Message):
    await message.answer("سلام! برای ثبت نام، یکی از گزینه‌ها را بزنید:", reply_markup=start_kb)

@router.message(F.text == "📝 فرم ساده")
async def open_form(message: types.Message, state: FSMContext):
    await state.set_state(Form.name)
    await message.answer("لطفاً نام خود را بنویسید:", reply_markup=types.ReplyKeyboardRemove())

@router.message(Form.name)
async def got_name(message: types.Message, state: FSMContext):
    await state.clear()
    await process_name_submission(message.from_user, message.text, message)

@router.message(F.web_app_data)
async def on_webapp_payload(message: types.Message):
    try: payload = json.loads(message.web_app_data.data or "{}")
    except Exception: payload = {}
    name = payload.get("name", "")
    await process_name_submission(message.from_user, name, message)

@router.callback_query(F.data.startswith("approve:"))
async def approve_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    info = PENDING.pop(token, None)
    if not info:
        await call.answer("درخواست یافت نشد/قبلاً بررسی شده.", show_alert=True); return
    if TARGET_GROUP_ID == 0:
        await call.answer("TARGET_GROUP_ID هنوز تنظیم نشده.", show_alert=True); return
    text = f"📨 درخواست تایید‌شده\nنام: {html.quote(info['name'])}\nuser_id: {info['user_id']}"
    try:
        await bot.send_message(TARGET_GROUP_ID, text)
        await bot.send_message(info["user_id"], "✅ فرم شما تایید شد و به گروه ارسال شد.")
        await call.message.edit_text(call.message.text + "\n\n✅ ارسال شد به گروه.")
        await call.answer("ارسال شد.")
    except Exception:
        await call.answer("خطا در ارسال به گروه.", show_alert=True)

@router.callback_query(F.data.startswith("reject:"))
async def reject_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("شما ادمین نیستید.", show_alert=True); return
    token = call.data.split(":", 1)[1]
    info = PENDING.pop(token, None)
    if not info:
        await call.answer("درخواست یافت نشد.", show_alert=True); return
    try: await bot.send_message(info["user_id"], "❌ فرم شما رد شد.")
    except Exception: pass
    await call.message.edit_text(call.message.text + "\n\n❌ رد شد.")
    await call.answer("رد شد.")

@router.message(Command("me"))
async def cmd_me(message: types.Message):
    await message.answer(f"your user_id: {message.from_user.id}")

@router.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"chat_id: {message.chat.id}\nchat_type: {message.chat.type}")

async def main():
    if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN در .env تنظیم نشده است.")
    print("Bot is running…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
PY
