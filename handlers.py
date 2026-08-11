from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import db
import keyboards as kb

router = Router()

ALL_ITEMS = {}
for k, v in kb.STARS_PACKAGES.items():
    ALL_ITEMS[k] = ("استارز", f"{v[0]} استارز", v[1])
for k, v in kb.GIFT_ITEMS.items():
    ALL_ITEMS[k] = ("گیفت", v[0], v[1])
for k, v in kb.PREMIUM_PLANS.items():
    ALL_ITEMS[k] = ("پرمیوم", f"پرمیوم {v[0]}", v[1])


class ChargeState(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()


# ---------------- START ----------------
@router.message(CommandStart())
async def cmd_start(message: Message, command: Command = None):
    referrer_id = None
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            referrer_id = int(args[1][3:])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    await db.get_or_create_user(message.from_user.id, message.from_user.username or "", referrer_id)

    text = (
        "🐾 به <b>Dogg Starz | داگ استارز</b> خوش اومدی!\n\n"
        "از منوی زیر می‌تونی استارز، گیفت و پرمیوم تلگرام رو با بهترین قیمت بخری. ✅\n"
        "خرید امن، سریع و با پشتیبانی ۲۴ ساعته 🐶"
    )
    await message.answer(text, reply_markup=kb.main_menu())


# ---------------- بازگشت به منوی اصلی ----------------
@router.callback_query(F.data == "menu_main")
async def cb_main_menu(call: CallbackQuery):
    await call.message.edit_text(
        "🐾 <b>Dogg Starz | داگ استارز</b>\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=kb.main_menu()
    )
    await call.answer()


# ---------------- زیرمنوها ----------------
@router.callback_query(F.data == "menu_stars")
async def cb_stars(call: CallbackQuery):
    await call.message.edit_text("⭐ یکی از بسته‌های استارز رو انتخاب کن:", reply_markup=kb.stars_menu())
    await call.answer()


@router.callback_query(F.data == "menu_gift")
async def cb_gift(call: CallbackQuery):
    await call.message.edit_text("🎁 یکی از گیفت‌ها رو انتخاب کن:", reply_markup=kb.gift_menu())
    await call.answer()


@router.callback_query(F.data == "menu_premium")
async def cb_premium(call: CallbackQuery):
    await call.message.edit_text("⭐ یکی از پلن‌های پرمیوم رو انتخاب کن:", reply_markup=kb.premium_menu())
    await call.answer()


# ---------------- انتخاب آیتم برای خرید ----------------
@router.callback_query(F.data.in_(ALL_ITEMS.keys()))
async def cb_item_selected(call: CallbackQuery):
    category, name, price = ALL_ITEMS[call.data]
    text = (
        f"🧾 <b>{name}</b>\n"
        f"دسته: {category}\n"
        f"قیمت: <b>{price:,}</b> تومان\n\n"
        "برای تکمیل خرید، مبلغ از کیف پول شما کسر میشه. اگر موجودی کافی نداری اول باید حساب رو شارژ کنی."
    )
    await call.message.edit_text(text, reply_markup=kb.confirm_purchase(call.data))
    await call.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def cb_confirm_purchase(call: CallbackQuery, bot: Bot):
    item_key = call.data.replace("confirm_", "")
    category, name, price = ALL_ITEMS[item_key]

    user = await db.get_user(call.from_user.id)
    balance = user[2] if user else 0

    if balance < price:
        await call.answer("موجودی کافی نیست! اول حسابتو شارژ کن 💳", show_alert=True)
        return

    await db.update_balance(call.from_user.id, -price)
    order_id = await db.create_order(call.from_user.id, category, name, price)

    await call.message.edit_text(
        f"✅ سفارش شما ثبت شد!\n\n"
        f"شماره سفارش: <code>{order_id}</code>\n"
        f"آیتم: {name}\n"
        f"مبلغ: {price:,} تومان\n\n"
        "تیم پشتیبانی به‌زودی سفارش رو پردازش می‌کنه. وضعیتش رو از بخش «📦 پیگیری سفارش» ببین.",
        reply_markup=kb.back_button().as_markup()
    )
    await call.answer("سفارش ثبت شد ✅")

    if config.ADMIN_ID:
        await bot.send_message(
            config.ADMIN_ID,
            f"🆕 سفارش جدید\n"
            f"کاربر: {call.from_user.id} (@{call.from_user.username})\n"
            f"آیتم: {name}\n"
            f"مبلغ: {price:,} تومان\n"
            f"شماره سفارش: {order_id}",
            reply_markup=kb.admin_order_actions(order_id)
        )


# ---------------- حساب کاربری ----------------
@router.callback_query(F.data == "menu_account")
async def cb_account(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    balance = user[2] if user else 0
    ref_count = await db.count_referrals(call.from_user.id)

    text = (
        f"👤 <b>حساب کاربری</b>\n\n"
        f"آیدی عددی: <code>{call.from_user.id}</code>\n"
        f"موجودی کیف پول: <b>{balance:,}</b> تومان\n"
        f"تعداد زیرمجموعه‌ها: <b>{ref_count}</b> نفر"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- زیرمجموعه‌گیری ----------------
@router.callback_query(F.data == "menu_referral")
async def cb_referral(call: CallbackQuery, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{call.from_user.id}"
    ref_count = await db.count_referrals(call.from_user.id)
    text = (
        "🔗 <b>سیستم زیرمجموعه‌گیری</b>\n\n"
        "لینک اختصاصی خودتو به دوستات بفرست و با هر عضویت جایزه بگیر!\n\n"
        f"لینک شما:\n<code>{link}</code>\n\n"
        f"تعداد زیرمجموعه‌ها: {ref_count} نفر"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- پیگیری سفارش ----------------
@router.callback_query(F.data == "menu_orders")
async def cb_orders(call: CallbackQuery):
    orders = await db.get_user_orders(call.from_user.id)
    if not orders:
        text = "📦 هنوز هیچ سفارشی ثبت نکردی."
    else:
        status_map = {"pending": "⏳ در حال پردازش", "done": "✅ انجام‌شده", "cancelled": "❌ لغو‌شده"}
        lines = ["📦 <b>سفارش‌های اخیر شما</b>\n"]
        for order_id, category, item, price, status, created_at in orders:
            lines.append(f"• {item} - {price:,} تومان - {status_map.get(status, status)} - <code>{order_id}</code>")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- پشتیبانی ----------------
@router.callback_query(F.data == "menu_support")
async def cb_support(call: CallbackQuery):
    text = (
        "🆘 <b>پشتیبانی</b>\n\n"
        "برای هرگونه سوال یا مشکل، پیام خودتو همینجا برای ما بفرست، به زودی جواب می‌گیری.\n"
        "یا مستقیم با ادمین در ارتباط باش: @YourSupportUsername"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- افزایش موجودی ----------------
@router.callback_query(F.data == "menu_charge")
async def cb_charge_menu(call: CallbackQuery):
    await call.message.edit_text("💳 روش افزایش موجودی رو انتخاب کن:", reply_markup=kb.charge_menu())
    await call.answer()


@router.callback_query(F.data == "charge_gateway")
async def cb_charge_gateway(call: CallbackQuery):
    await call.answer("درگاه پرداخت آنلاین به‌زودی فعال میشه 🌐", show_alert=True)


@router.callback_query(F.data == "charge_card")
async def cb_charge_card(call: CallbackQuery, state: FSMContext):
    text = (
        "💳 <b>افزایش موجودی - کارت به کارت</b>\n\n"
        f"مبلغ دلخواه رو به شماره کارت زیر واریز کن:\n\n"
        f"<code>{config.CARD_NUMBER}</code>\n"
        f"به نام: {config.CARD_HOLDER}\n\n"
        "بعد از واریز، مبلغ واریزی رو به عدد (تومان) اینجا بفرست."
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await state.set_state(ChargeState.waiting_amount)
    await call.answer()


@router.message(ChargeState.waiting_amount)
async def receive_charge_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد مبلغ واریزی رو بفرست (مثلاً 200000).")
        return
    amount = int(message.text.strip())
    await state.update_data(amount=amount)
    await state.set_state(ChargeState.waiting_receipt)
    await message.answer("عکس رسید واریزی رو بفرست 📸")


@router.message(ChargeState.waiting_receipt, F.photo)
async def receive_charge_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    request_id = await db.create_charge_request(message.from_user.id, amount)
    await state.clear()

    await message.answer(
        f"✅ درخواست شارژ شما ثبت شد.\n"
        f"شماره پیگیری: <code>{request_id}</code>\n"
        "بعد از تایید ادمین، موجودی حسابت اضافه میشه."
    )

    if config.ADMIN_ID:
        await bot.send_photo(
            config.ADMIN_ID,
            photo=message.photo[-1].file_id,
            caption=(
                f"🆕 درخواست شارژ جدید\n"
                f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                f"مبلغ: {amount:,} تومان\n"
                f"شماره پیگیری: {request_id}"
            ),
            reply_markup=kb.admin_charge_actions(request_id)
        )


@router.message(ChargeState.waiting_receipt)
async def receive_charge_receipt_wrong(message: Message):
    await message.answer("لطفاً عکس رسید واریزی رو ارسال کن 📸")


# ---------------- اکشن‌های ادمین: تایید/رد شارژ ----------------
@router.callback_query(F.data.startswith("admincharge_"))
async def cb_admin_charge_action(call: CallbackQuery, bot: Bot):
    if call.from_user.id != config.ADMIN_ID:
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return

    _, action, request_id = call.data.split("_", 2)
    request_id = call.data.split("_", 2)[2]
    req = await db.get_charge_request(request_id)
    if not req:
        await call.answer("درخواست پیدا نشد.", show_alert=True)
        return

    _, user_id, amount, status = req
    if status != "pending":
        await call.answer("قبلاً بررسی شده.", show_alert=True)
        return

    if action == "ok":
        await db.update_balance(user_id, amount)
        await db.set_charge_status(request_id, "approved")
        await call.message.edit_caption(caption=call.message.caption + "\n\n✅ تایید شد و موجودی اضافه شد.")
        await bot.send_message(user_id, f"✅ شارژ حساب شما به مبلغ {amount:,} تومان تایید شد.")
    else:
        await db.set_charge_status(request_id, "rejected")
        await call.message.edit_caption(caption=call.message.caption + "\n\n❌ رد شد.")
        await bot.send_message(user_id, "❌ متاسفانه رسید واریزی شما تایید نشد. با پشتیبانی در ارتباط باش.")

    await call.answer()


# ---------------- اکشن‌های ادمین: تغییر وضعیت سفارش ----------------
@router.callback_query(F.data.startswith("adminorder_"))
async def cb_admin_order_action(call: CallbackQuery, bot: Bot):
    if call.from_user.id != config.ADMIN_ID:
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return

    parts = call.data.split("_", 2)
    action = parts[1]
    order_id = parts[2]

    order = await db.get_order(order_id)
    if not order:
        await call.answer("سفارش پیدا نشد.", show_alert=True)
        return

    _, user_id, category, item, price, status = order

    if action == "done":
        await db.set_order_status(order_id, "done")
        await call.message.edit_text(call.message.text + "\n\n✅ انجام شد.")
        await bot.send_message(user_id, f"✅ سفارش شما ({item}) با موفقیت انجام شد. ممنون از خریدت 🐾")
    else:
        await db.set_order_status(order_id, "cancelled")
        await db.update_balance(user_id, price)  # برگشت وجه به کیف پول
        await call.message.edit_text(call.message.text + "\n\n❌ لغو شد و مبلغ به کیف پول کاربر برگشت.")
        await bot.send_message(user_id, f"❌ سفارش شما ({item}) لغو شد و مبلغ به کیف پولت برگشت داده شد.")

    await call.answer()
