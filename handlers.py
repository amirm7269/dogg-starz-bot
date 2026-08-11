from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import db
import keyboards as kb

router = Router()


def is_admin(user_id: int) -> bool:
    return config.ADMIN_ID != 0 and user_id == config.ADMIN_ID


class ChargeState(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()


class AdminState(StatesGroup):
    waiting_new_price = State()      # data: product_id
    waiting_new_name = State()       # data: product_id
    waiting_new_item_name = State()  # data: category
    waiting_new_item_price = State() # data: category, name


GIFT_BULK_ITEMS = [
    # گیفت‌های عادی
    ("💝 گیفت قلب", 7000),
    ("🧸 گیفت تدی", 7000),
    ("🎁 گیفت کادو", 12000),
    ("🌹 گیفت گل رز", 12000),
    ("🎂 گیفت کیک", 23000),
    ("🌸 گیفت گل", 23000),
    ("🍾 گیفت بطری", 23000),
    ("🚀 گیفت سفینه", 23000),
    ("🏆 گیفت جام", 45000),
    ("💍 گیفت حلقه", 45000),
    ("💎 گیفت الماس", 45000),
    # گیفت‌های مناسبتی
    ("🐰 تدی خرگوشی", 23000),
    ("🎄 تدی درخت کاج", 23000),
    ("🎅 گیفت تدی نوئل", 23000),
    ("⚽ گیفت لیونل تدی", 23000),
    ("🤡 گیفت تدی دلقک", 23000),
    ("🍀 گیفت تدی پیلدار", 23000),
    ("🌸 گیفت تدی صورتی", 23000),
    ("👷 گیفت تدی مهندس", 23000),
    ("💝 گیفت قلب ولنتاین", 23000),
    ("🧸 گیفت خرس ولنتاین", 23000),
]


# ---------------- START ----------------
@router.message(CommandStart())
async def cmd_start(message: Message):
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
    await message.answer(text, reply_markup=kb.main_menu(is_admin(message.from_user.id)))


# ---------------- افزودن دسته‌ای گیفت‌های آماده (فقط ادمین) ----------------
@router.message(Command("addgifts"))
async def cmd_add_gifts(message: Message):
    if not is_admin(message.from_user.id):
        return

    existing = await db.get_products("gift")
    existing_names = {name for (_id, name, _price) in existing}

    added = 0
    for name, price in GIFT_BULK_ITEMS:
        if name in existing_names:
            continue
        await db.add_product("gift", name, price)
        added += 1

    await message.answer(
        f"✅ {added} گیفت جدید اضافه شد.\n"
        f"{len(GIFT_BULK_ITEMS) - added} تای دیگه از قبل موجود بودن.\n\n"
        "از منوی «🎁 خرید گیفت» یا «⚙️ پنل مدیریت → مدیریت گیفت» می‌تونی ببینی‌شون."
    )


# ---------------- بازگشت به منوی اصلی ----------------
@router.callback_query(F.data == "menu_main")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🐾 <b>Dogg Starz | داگ استارز</b>\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=kb.main_menu(is_admin(call.from_user.id))
    )
    await call.answer()


# ---------------- زیرمنوهای خرید ----------------
@router.callback_query(F.data == "menu_stars")
async def cb_stars(call: CallbackQuery):
    products = await db.get_products("stars")
    await call.message.edit_text("⭐ یکی از بسته‌های استارز رو انتخاب کن:", reply_markup=kb.category_menu("stars", products))
    await call.answer()


@router.callback_query(F.data == "menu_gift")
async def cb_gift(call: CallbackQuery):
    products = await db.get_products("gift")
    await call.message.edit_text("🎁 یکی از گیفت‌ها رو انتخاب کن:", reply_markup=kb.category_menu("gift", products))
    await call.answer()


@router.callback_query(F.data == "menu_premium")
async def cb_premium(call: CallbackQuery):
    products = await db.get_products("premium")
    await call.message.edit_text("⭐ یکی از پلن‌های پرمیوم رو انتخاب کن:", reply_markup=kb.category_menu("premium", products))
    await call.answer()


# ---------------- انتخاب آیتم برای خرید ----------------
@router.callback_query(F.data.startswith("item_"))
async def cb_item_selected(call: CallbackQuery):
    product_id = int(call.data.replace("item_", ""))
    product = await db.get_product(product_id)
    if not product:
        await call.answer("این آیتم دیگه موجود نیست.", show_alert=True)
        return

    _, category, name, price = product
    text = (
        f"🧾 <b>{name}</b>\n"
        f"قیمت: <b>{price:,}</b> تومان\n\n"
        "برای تکمیل خرید، مبلغ از کیف پول شما کسر میشه. اگر موجودی کافی نداری اول باید حساب رو شارژ کنی."
    )
    await call.message.edit_text(text, reply_markup=kb.confirm_purchase(product_id))
    await call.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def cb_confirm_purchase(call: CallbackQuery, bot: Bot):
    product_id = int(call.data.replace("confirm_", ""))
    product = await db.get_product(product_id)
    if not product:
        await call.answer("این آیتم دیگه موجود نیست.", show_alert=True)
        return
    _, category, name, price = product

    user = await db.get_user(call.from_user.id)
    balance = user[2] if user else 0

    if balance < price:
        await call.answer("موجودی کافی نیست! اول حسابتو شارژ کن 💳", show_alert=True)
        return

    await db.update_balance(call.from_user.id, -price)
    order_id = await db.create_order(call.from_user.id, kb.CATEGORY_LABELS.get(category, category), name, price)

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
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return

    request_id = call.data.split("_", 2)[2]
    action = call.data.split("_", 2)[1]
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
    if not is_admin(call.from_user.id):
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
        await db.update_balance(user_id, price)
        await call.message.edit_text(call.message.text + "\n\n❌ لغو شد و مبلغ به کیف پول کاربر برگشت.")
        await bot.send_message(user_id, f"❌ سفارش شما ({item}) لغو شد و مبلغ به کیف پولت برگشت داده شد.")

    await call.answer()


# ==================== پنل مدیریت محصولات (فقط ادمین) ====================

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "⚙️ <b>پنل مدیریت</b>\nکدوم بخش رو می‌خوای مدیریت کنی؟",
        reply_markup=kb.admin_panel_menu()
    )
    await call.answer()


@router.callback_query(F.data.startswith("admincat_"))
async def cb_admin_category(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    category = call.data.replace("admincat_", "")
    products = await db.get_products(category)
    label = kb.CATEGORY_LABELS.get(category, category)
    text = f"📋 <b>مدیریت {label}</b>\nروی هر آیتم بزن تا ویرایش/حذفش کنی، یا آیتم جدید اضافه کن."
    if not products:
        text += "\n\nهنوز آیتمی اضافه نشده."
    await call.message.edit_text(text, reply_markup=kb.admin_category_menu(category, products))
    await call.answer()


@router.callback_query(F.data.startswith("adminedit_"))
async def cb_admin_edit_item(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    product_id = int(call.data.replace("adminedit_", ""))
    product = await db.get_product(product_id)
    if not product:
        await call.answer("این آیتم دیگه وجود نداره.", show_alert=True)
        return
    _, category, name, price = product
    text = f"🧾 <b>{name}</b>\nقیمت فعلی: <b>{price:,}</b> تومان\n\nچیکار می‌خوای بکنی؟"
    await call.message.edit_text(text, reply_markup=kb.admin_item_actions(product_id, category))
    await call.answer()


@router.callback_query(F.data.startswith("adminprice_"))
async def cb_admin_price_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    product_id = int(call.data.replace("adminprice_", ""))
    await state.update_data(product_id=product_id)
    await state.set_state(AdminState.waiting_new_price)
    await call.message.edit_text("💰 قیمت جدید رو به تومان بفرست (فقط عدد، مثلاً 250000):")
    await call.answer()


@router.message(AdminState.waiting_new_price)
async def admin_receive_new_price(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست (مثلاً 250000).")
        return
    data = await state.get_data()
    product_id = data.get("product_id")
    new_price = int(message.text.strip())

    await db.update_product_price(product_id, new_price)
    product = await db.get_product(product_id)
    await state.clear()

    if product:
        _, category, name, price = product
        await message.answer(
            f"✅ قیمت «{name}» به {price:,} تومان تغییر کرد.",
            reply_markup=kb.admin_item_actions(product_id, category)
        )
    else:
        await message.answer("✅ قیمت به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("adminname_"))
async def cb_admin_name_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    product_id = int(call.data.replace("adminname_", ""))
    await state.update_data(product_id=product_id)
    await state.set_state(AdminState.waiting_new_name)
    await call.message.edit_text("✏️ نام جدید آیتم رو بفرست:")
    await call.answer()


@router.message(AdminState.waiting_new_name)
async def admin_receive_new_name(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("لطفاً یه نام معتبر بفرست.")
        return
    data = await state.get_data()
    product_id = data.get("product_id")
    new_name = message.text.strip()

    await db.update_product_name(product_id, new_name)
    product = await db.get_product(product_id)
    await state.clear()

    if product:
        _, category, name, price = product
        await message.answer(
            f"✅ نام آیتم به «{name}» تغییر کرد.",
            reply_markup=kb.admin_item_actions(product_id, category)
        )
    else:
        await message.answer("✅ نام به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("admindelok_"))
async def cb_admin_delete_confirmed(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    product_id = int(call.data.replace("admindelok_", ""))
    product = await db.get_product(product_id)
    category = product[1] if product else "stars"

    await db.delete_product(product_id)
    products = await db.get_products(category)
    label = kb.CATEGORY_LABELS.get(category, category)
    await call.message.edit_text(
        f"🗑 آیتم حذف شد.\n\n📋 <b>مدیریت {label}</b>",
        reply_markup=kb.admin_category_menu(category, products)
    )
    await call.answer("حذف شد ✅")


@router.callback_query(F.data.startswith("admindel_"))
async def cb_admin_delete_ask(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    product_id = int(call.data.replace("admindel_", ""))
    product = await db.get_product(product_id)
    if not product:
        await call.answer("این آیتم دیگه وجود نداره.", show_alert=True)
        return
    _, category, name, price = product
    await call.message.edit_text(
        f"⚠️ مطمئنی می‌خوای «{name}» رو حذف کنی؟",
        reply_markup=kb.admin_delete_confirm(product_id, category)
    )
    await call.answer()


@router.callback_query(F.data.startswith("adminadd_"))
async def cb_admin_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    category = call.data.replace("adminadd_", "")
    await state.update_data(category=category)
    await state.set_state(AdminState.waiting_new_item_name)
    await call.message.edit_text("➕ نام آیتم جدید رو بفرست (مثلاً: 5000 استارز):")
    await call.answer()


@router.message(AdminState.waiting_new_item_name)
async def admin_receive_item_name(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("لطفاً یه نام معتبر بفرست.")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminState.waiting_new_item_price)
    await message.answer("💰 حالا قیمت این آیتم رو به تومان بفرست (فقط عدد):")


@router.message(AdminState.waiting_new_item_price)
async def admin_receive_item_price(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست (مثلاً 250000).")
        return
    data = await state.get_data()
    category = data.get("category")
    name = data.get("name")
    price = int(message.text.strip())

    await db.add_product(category, name, price)
    await state.clear()

    products = await db.get_products(category)
    label = kb.CATEGORY_LABELS.get(category, category)
    await message.answer(
        f"✅ آیتم «{name}» با قیمت {price:,} تومان اضافه شد.\n\n📋 <b>مدیریت {label}</b>",
        reply_markup=kb.admin_category_menu(category, products)
    )
