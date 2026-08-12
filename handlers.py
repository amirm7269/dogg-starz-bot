from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InputMediaPhoto, InputMediaVideo
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import db
import keyboards as kb

router = Router()


# ---------------- گرفتن آیدی عددی یه چنل (برای تنظیم CHARGE_CHANNEL_ID) ----------------
# کافیه ربات رو ادمین چنل کنید و توی چنل بنویسید: /id
@router.channel_post(F.text == "/id")
async def channel_get_id(message: Message):
    await message.answer(f"🆔 آیدی عددی این چنل:\n<code>{message.chat.id}</code>")


def is_admin(user_id: int) -> bool:
    return config.ADMIN_ID != 0 and user_id == config.ADMIN_ID


DAILY_CHARGE_LIMIT = 500_000  # سقف مجاز واریز روزانه بدون احراز هویت (تومان)

KYC_INSTRUCTIONS = (
    "⚠️ <b>مبلغی که وارد کردی بیشتر از سقف مجاز روزانه (500,000 تومان) هست.</b>\n\n"
    "برای واریزهای بالای این سقف، برای جلوگیری از کلاهبرداری، نیاز به احراز هویت داری. مدارک لازم:\n\n"
    "1️⃣ عکس روی کارتی که باهاش واریز می‌کنی\n"
    "2️⃣ عکس شناسنامه (یا کارت ملی) دارنده‌ی همون کارت\n"
    "3️⃣ یه ویدیوی کوتاه از همون فرد (که عکسش توی شناسنامه هست) در حالی که می‌گه:\n"
    "«بنده در حال خرید از فروشگاه داگ استارز هستم»\n\n"
    "لطفاً اول 📸 عکس کارتت رو بفرست:"
)


class ChargeState(StatesGroup):
    waiting_amount = State()
    waiting_card_photo = State()   # data: amount
    waiting_phone = State()        # data: amount, card_photo_id
    waiting_receipt = State()      # data: amount, card_photo_id, phone


class KycState(StatesGroup):
    waiting_card_photo = State()   # data: amount
    waiting_id_photo = State()     # data: amount, card_photo_id
    waiting_video = State()        # data: amount, card_photo_id, id_photo_id
    waiting_receipt = State()      # data: amount, card_photo_id, id_photo_id, video_id


class AdminState(StatesGroup):
    waiting_new_price = State()      # data: product_id
    waiting_new_name = State()       # data: product_id
    waiting_new_item_name = State()  # data: category
    waiting_new_item_price = State() # data: category, name
    waiting_stars_unit_price = State()
    waiting_new_text = State()       # data: text_key


class CustomStarsState(StatesGroup):
    waiting_qty = State()


DEFAULT_STARS_UNIT_PRICE = 450  # تومان به‌ازای هر استارز (پیش‌فرض، از پنل مدیریت قابل تغییره)


# ---------------- متن‌های قابل‌ویرایش ربات (از پنل مدیریت) ----------------
TEXT_DEFAULTS = {
    "welcome": (
        "✨ ━━━━━━━━━━━━━━ ✨\n"
        "🐾 <b>Dogg Starz | داگ استارز</b> 🐾\n"
        "✨ ━━━━━━━━━━━━━━ ✨\n\n"
        "به فروشگاه رسمی <b>استارز، گیفت و پرمیوم تلگرام</b> خوش اومدی! 🎉\n\n"
        "🛡 <b>خرید ۱۰۰٪ امن و تضمینی</b>\n"
        "⚡️ <b>تحویل سریع و آنی</b>\n"
        "🕐 <b>پشتیبانی ۲۴ ساعته</b>\n\n"
        "👇 یکی از گزینه‌های زیر رو انتخاب کن:"
    ),
    "menu_main": (
        "✨ ━━━━━━━━━━━━━━ ✨\n"
        "🐾 <b>Dogg Starz | داگ استارز</b> 🐾\n"
        "✨ ━━━━━━━━━━━━━━ ✨\n\n"
        "👇 یکی از گزینه‌های زیر رو انتخاب کن:"
    ),
    "stars_menu": (
        "⭐️ ━━━━━━━━━━━━━━ ⭐️\n"
        "<b>خرید استارز تلگرام</b>\n"
        "⭐️ ━━━━━━━━━━━━━━ ⭐️\n\n"
        "یکی از بسته‌های زیر رو انتخاب کن، یا تعداد دلخواه خودت رو وارد کن:"
    ),
    "gift_menu": (
        "🎁 ━━━━━━━━━━━━━━ 🎁\n"
        "<b>خرید گیفت تلگرام</b>\n"
        "🎁 ━━━━━━━━━━━━━━ 🎁\n\n"
        "با ارسال گیفت، لبخند رو به دوستات هدیه بده 💫\n"
        "کدوم دسته رو می‌خوای؟"
    ),
    "gift_special_menu": (
        "🎊 <b>گیفت های مناسبتی</b> 🎊\n\n"
        "مخصوص کریسمس، ولنتاین و مناسبت‌های خاص 🎄💝\n"
        "لطفاً گیفت مورد نظرت رو انتخاب کن:"
    ),
    "gift_normal_menu": (
        "🧸 <b>گیفت های عادی</b> 🧸\n\n"
        "گیفت‌های محبوب برای هر روز 🎂🌹\n"
        "لطفاً گیفت مورد نظرت رو انتخاب کن:"
    ),
    "premium_menu": (
        "⭐️ ━━━━━━━━━━━━━━ ⭐️\n"
        "<b>خرید پرمیوم تلگرام</b>\n"
        "⭐️ ━━━━━━━━━━━━━━ ⭐️\n\n"
        "با پرمیوم به امکانات ویژه تلگرام دسترسی پیدا کن 🚀\n"
        "یکی از پلن‌ها رو انتخاب کن:"
    ),
    "referral_intro": (
        "🔗 ━━━━━━━━━━━━━━ 🔗\n"
        "<b>سیستم زیرمجموعه‌گیری</b>\n"
        "🔗 ━━━━━━━━━━━━━━ 🔗\n\n"
        "💸 لینک اختصاصی خودتو به دوستات بفرست و با هر عضویت جایزه بگیر!"
    ),
    "orders_empty": "📦 هنوز هیچ سفارشی ثبت نکردی.\n\nاز منوی اصلی یه خرید انجام بده تا اینجا نمایش داده بشه 🛍",
    "support": (
        "🆘 ━━━━━━━━━━━━━━ 🆘\n"
        "<b>پشتیبانی</b>\n"
        "🆘 ━━━━━━━━━━━━━━ 🆘\n\n"
        "برای هرگونه سوال یا مشکل، پیامتو همینجا برامون بفرست، به‌زودی جواب می‌گیری 💬\n\n"
        "یا مستقیم با ادمین در ارتباط باش: @YourSupportUsername"
    ),
    "charge_menu": (
        "💳 ━━━━━━━━━━━━━━ 💳\n"
        "<b>افزایش موجودی کیف پول</b>\n"
        "💳 ━━━━━━━━━━━━━━ 💳\n\n"
        "روش دلخواهت رو انتخاب کن:"
    ),
}

TEXT_LABELS = {
    "welcome": "👋 پیام خوش‌آمدگویی (استارت)",
    "menu_main": "🏠 پیام منوی اصلی",
    "stars_menu": "⭐️ پیام صفحه‌ی خرید استارز",
    "gift_menu": "🎁 پیام صفحه‌ی انتخاب نوع گیفت",
    "gift_special_menu": "🎊 پیام گیفت‌های مناسبتی",
    "gift_normal_menu": "🧸 پیام گیفت‌های عادی",
    "premium_menu": "💎 پیام صفحه‌ی خرید پرمیوم",
    "referral_intro": "🔗 متن ابتدای صفحه‌ی زیرمجموعه‌گیری",
    "orders_empty": "📦 پیام وقتی سفارشی نداری",
    "support": "🆘 پیام پشتیبانی",
    "charge_menu": "💳 پیام صفحه‌ی افزایش موجودی",
}


async def get_text(key: str) -> str:
    return await db.get_setting(f"text_{key}", TEXT_DEFAULTS.get(key, ""))


GIFT_SPECIAL_ITEMS = [
    ("🐰 گیفت تدی خرگوشی", 23000),
    ("🎄 گیفت تدی درخت کاج", 23000),
    ("🎅 گیفت تدی نوئل", 23000),
    ("🧸 گیفت لیونل تدی", 23000),
    ("🤡 گیفت تدی دلقک", 23000),
    ("🍀 گیفت تدی پیلدار", 23000),
    ("🌸 گیفت تدی صورتی", 23000),
    ("👷 گیفت تدی مهندس", 23000),
    ("💝 گیفت قلب ولن", 23000),
    ("🧸 گیفت خرس ولن", 23000),
]

GIFT_NORMAL_ITEMS = [
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

    text = await get_text("welcome")
    await message.answer(text, reply_markup=kb.main_menu(is_admin(message.from_user.id)))


# ---------------- افزودن دسته‌ای گیفت‌های آماده (فقط ادمین) ----------------
@router.message(Command("addgifts"))
async def cmd_add_gifts(message: Message):
    if not is_admin(message.from_user.id):
        return

    # پاکسازی گیفت‌های قدیمی که با ساختار قبلی (دسته‌بندی‌نشده) اضافه شده بودن
    old_gifts = await db.get_products("gift")
    for product_id, _name, _price in old_gifts:
        await db.delete_product(product_id)

    added = 0
    existing_special = {name for (_id, name, _price) in await db.get_products("gift_special")}
    for name, price in GIFT_SPECIAL_ITEMS:
        if name in existing_special:
            continue
        await db.add_product("gift_special", name, price)
        added += 1

    existing_normal = {name for (_id, name, _price) in await db.get_products("gift_normal")}
    for name, price in GIFT_NORMAL_ITEMS:
        if name in existing_normal:
            continue
        await db.add_product("gift_normal", name, price)
        added += 1

    total = len(GIFT_SPECIAL_ITEMS) + len(GIFT_NORMAL_ITEMS)
    await message.answer(
        f"✅ {added} گیفت جدید اضافه شد (از {total} تا).\n"
        f"{total - added} تای دیگه از قبل موجود بودن.\n\n"
        "از منوی «🎁 خرید گیفت» یا «⚙️ پنل مدیریت» می‌تونی ببینی‌شون."
    )


# ---------------- بازگشت به منوی اصلی ----------------
@router.callback_query(F.data == "menu_main")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = await get_text("menu_main")
    await call.message.edit_text(text, reply_markup=kb.main_menu(is_admin(call.from_user.id)))
    await call.answer()


# ---------------- زیرمنوهای خرید ----------------
@router.callback_query(F.data == "menu_stars")
async def cb_stars(call: CallbackQuery):
    products = await db.get_products("stars")
    text = await get_text("stars_menu")
    await call.message.edit_text(text, reply_markup=kb.category_menu("stars", products, show_custom_stars=True))
    await call.answer()


# ---------------- خرید تعداد دلخواه استارز ----------------
@router.callback_query(F.data == "stars_custom")
async def cb_stars_custom(call: CallbackQuery, state: FSMContext):
    text = (
        "🔢 <b>خرید تعداد دلخواه استارز</b>\n\n"
        "تعداد استارزی که می‌خوای رو بفرست (حداقل 50 عدد):"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button("menu_stars").as_markup())
    await state.set_state(CustomStarsState.waiting_qty)
    await call.answer()


@router.message(CustomStarsState.waiting_qty)
async def receive_custom_stars_qty(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست (مثلاً 200).")
        return

    qty = int(message.text.strip())
    if qty < 50:
        await message.answer("حداقل تعداد قابل خرید 50 استارزه. یه عدد بزرگ‌تر یا مساوی 50 بفرست.")
        return

    unit_price = int(await db.get_setting("stars_unit_price", DEFAULT_STARS_UNIT_PRICE))
    total_price = qty * unit_price
    await state.clear()

    text = (
        "🧾 ━━━━━━━━━━━━━━ 🧾\n"
        f"<b>{qty:,} استارز</b>\n"
        "🧾 ━━━━━━━━━━━━━━ 🧾\n\n"
        f"💱 قیمت هر استارز: {unit_price:,} تومان\n"
        f"💰 مبلغ کل: <b>{total_price:,}</b> تومان\n\n"
        "برای تکمیل خرید، مبلغ از کیف پولت کسر میشه."
    )
    await message.answer(text, reply_markup=kb.confirm_custom_stars(qty))


@router.callback_query(F.data.startswith("confirmcustom_"))
async def cb_confirm_custom_stars(call: CallbackQuery, bot: Bot):
    qty = int(call.data.replace("confirmcustom_", ""))
    unit_price = int(await db.get_setting("stars_unit_price", DEFAULT_STARS_UNIT_PRICE))
    total_price = qty * unit_price

    user = await db.get_user(call.from_user.id)
    balance = user[2] if user else 0

    if balance < total_price:
        await call.answer("موجودی کافی نیست! اول حسابتو شارژ کن 💳", show_alert=True)
        return

    item_name = f"{qty:,} استارز (تعداد دلخواه)"
    await db.update_balance(call.from_user.id, -total_price)
    order_id = await db.create_order(call.from_user.id, "استارز", item_name, total_price)

    await call.message.edit_text(
        "✅ ━━━━━━━━━━━━━━ ✅\n"
        "<b>سفارش شما با موفقیت ثبت شد!</b>\n"
        "✅ ━━━━━━━━━━━━━━ ✅\n\n"
        f"🔖 شماره سفارش: <code>{order_id}</code>\n"
        f"⭐️ آیتم: {item_name}\n"
        f"💰 مبلغ: {total_price:,} تومان\n\n"
        "⏳ تیم پشتیبانی به‌زودی سفارش رو پردازش می‌کنه.",
        reply_markup=kb.back_button().as_markup()
    )
    await call.answer("سفارش ثبت شد ✅")

    order_target = config.ORDER_CHANNEL_ID if config.ORDER_CHANNEL_ID else config.ADMIN_ID
    if order_target:
        await bot.send_message(
            order_target,
            f"🆕 سفارش جدید (تعداد دلخواه)\n"
            f"کاربر: {call.from_user.id} (@{call.from_user.username})\n"
            f"آیتم: {item_name}\n"
            f"مبلغ: {total_price:,} تومان\n"
            f"شماره سفارش: {order_id}",
            reply_markup=kb.admin_order_actions(order_id)
        )


@router.callback_query(F.data == "menu_gift")
async def cb_gift(call: CallbackQuery):
    text = await get_text("gift_menu")
    await call.message.edit_text(text, reply_markup=kb.gift_type_menu())
    await call.answer()


@router.callback_query(F.data == "menu_gift_special")
async def cb_gift_special(call: CallbackQuery):
    products = await db.get_products("gift_special")
    text = await get_text("gift_special_menu")
    await call.message.edit_text(
        text,
        reply_markup=kb.category_menu("gift_special", products, back_target="menu_gift")
    )
    await call.answer()


@router.callback_query(F.data == "menu_gift_normal")
async def cb_gift_normal(call: CallbackQuery):
    products = await db.get_products("gift_normal")
    text = await get_text("gift_normal_menu")
    await call.message.edit_text(
        text,
        reply_markup=kb.category_menu("gift_normal", products, back_target="menu_gift")
    )
    await call.answer()


@router.callback_query(F.data == "menu_premium")
async def cb_premium(call: CallbackQuery):
    products = await db.get_products("premium")
    text = await get_text("premium_menu")
    await call.message.edit_text(text, reply_markup=kb.category_menu("premium", products))
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
        "🧾 ━━━━━━━━━━━━━━ 🧾\n"
        f"<b>{name}</b>\n"
        "🧾 ━━━━━━━━━━━━━━ 🧾\n\n"
        f"💰 قیمت: <b>{price:,}</b> تومان\n\n"
        "برای تکمیل خرید، مبلغ از کیف پولت کسر میشه.\n"
        "اگه موجودی کافی نداری، اول از «💳 افزایش موجودی» شارژ کن."
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
        "✅ ━━━━━━━━━━━━━━ ✅\n"
        "<b>سفارش شما با موفقیت ثبت شد!</b>\n"
        "✅ ━━━━━━━━━━━━━━ ✅\n\n"
        f"🔖 شماره سفارش: <code>{order_id}</code>\n"
        f"🎁 آیتم: {name}\n"
        f"💰 مبلغ: {price:,} تومان\n\n"
        "⏳ تیم پشتیبانی به‌زودی سفارش رو پردازش می‌کنه.\n"
        "وضعیتش رو از «📦 پیگیری سفارش» چک کن.",
        reply_markup=kb.back_button().as_markup()
    )
    await call.answer("سفارش ثبت شد ✅")

    order_target = config.ORDER_CHANNEL_ID if config.ORDER_CHANNEL_ID else config.ADMIN_ID
    if order_target:
        await bot.send_message(
            order_target,
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
        "👤 ━━━━━━━━━━━━━━ 👤\n"
        "<b>حساب کاربری شما</b>\n"
        "👤 ━━━━━━━━━━━━━━ 👤\n\n"
        f"🆔 آیدی عددی: <code>{call.from_user.id}</code>\n"
        f"💰 موجودی کیف پول: <b>{balance:,}</b> تومان\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{ref_count}</b> نفر"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- زیرمجموعه‌گیری ----------------
@router.callback_query(F.data == "menu_referral")
async def cb_referral(call: CallbackQuery, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{call.from_user.id}"
    ref_count = await db.count_referrals(call.from_user.id)
    intro = await get_text("referral_intro")
    text = (
        f"{intro}\n\n"
        f"🔗 لینک شما:\n<code>{link}</code>\n\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{ref_count}</b> نفر"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- پیگیری سفارش ----------------
@router.callback_query(F.data == "menu_orders")
async def cb_orders(call: CallbackQuery):
    orders = await db.get_user_orders(call.from_user.id)
    if not orders:
        text = await get_text("orders_empty")
    else:
        status_map = {"pending": "⏳ در حال پردازش", "done": "✅ انجام‌شده", "cancelled": "❌ لغو‌شده"}
        lines = ["📦 ━━━━━━━━━━━━━━ 📦", "<b>سفارش‌های اخیر شما</b>", "📦 ━━━━━━━━━━━━━━ 📦\n"]
        for order_id, category, item, price, status, created_at in orders:
            lines.append(f"🔸 {item} — {price:,} تومان\n{status_map.get(status, status)} | <code>{order_id}</code>\n")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- پشتیبانی ----------------
@router.callback_query(F.data == "menu_support")
async def cb_support(call: CallbackQuery):
    text = await get_text("support")
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await call.answer()


# ---------------- افزایش موجودی ----------------
@router.callback_query(F.data == "menu_charge")
async def cb_charge_menu(call: CallbackQuery):
    text = await get_text("charge_menu")
    await call.message.edit_text(text, reply_markup=kb.charge_menu())
    await call.answer()


@router.callback_query(F.data == "charge_gateway")
async def cb_charge_gateway(call: CallbackQuery):
    await call.answer("درگاه پرداخت آنلاین به‌زودی فعال میشه 🌐", show_alert=True)


@router.callback_query(F.data == "charge_card")
async def cb_charge_card(call: CallbackQuery, state: FSMContext):
    text = (
        "💳 <b>افزایش موجودی — کارت به کارت</b>\n\n"
        f"🔸 سقف مجاز واریز روزانه بدون احراز هویت: <b>{DAILY_CHARGE_LIMIT:,} تومان</b>\n"
        "🔸 برای مبالغ بالاتر، نیاز به احراز هویت داری (در مرحله بعد توضیح میدم).\n\n"
        "لطفاً مبلغی که می‌خوای واریز کنی رو به عدد (تومان) بفرست:"
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

    if amount > DAILY_CHARGE_LIMIT:
        await state.update_data(amount=amount)
        await state.set_state(KycState.waiting_card_photo)
        await message.answer(KYC_INSTRUCTIONS)
        return

    await state.update_data(amount=amount)
    await state.set_state(ChargeState.waiting_card_photo)
    text = (
        f"مبلغ رو به شماره کارت زیر واریز کن:\n\n"
        f"💳 <code>{config.CARD_NUMBER}</code>\n"
        f"👤 به نام: {config.CARD_HOLDER}\n\n"
        "📸 حالا برای جلوگیری از کلاهبرداری، عکس روی کارتی که باهاش واریز می‌کنی رو بفرست:"
    )
    await message.answer(text)


@router.message(ChargeState.waiting_card_photo, F.photo)
async def receive_charge_card_photo(message: Message, state: FSMContext):
    await state.update_data(card_photo_id=message.photo[-1].file_id)
    await state.set_state(ChargeState.waiting_phone)

    contact_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 ارسال شماره تلفنم", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "📱 حالا لطفاً با دکمه‌ی زیر، شماره تلفن اکانتی که باهاش داری خرید می‌کنی رو برامون بفرست:",
        reply_markup=contact_kb
    )


@router.message(ChargeState.waiting_card_photo)
async def receive_charge_card_photo_wrong(message: Message):
    await message.answer("لطفاً عکس کارتت رو ارسال کن 📸")


@router.message(ChargeState.waiting_phone, F.contact)
async def receive_charge_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(ChargeState.waiting_receipt)
    await message.answer(
        "✅ شماره دریافت شد.\n\n📸 حالا عکس رسید واریزی رو بفرست:",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(ChargeState.waiting_phone)
async def receive_charge_phone_wrong(message: Message):
    await message.answer("لطفاً از دکمه‌ی «📱 ارسال شماره تلفنم» استفاده کن تا شماره‌ت ثبت بشه.")


@router.message(ChargeState.waiting_receipt, F.photo)
async def receive_charge_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    card_photo_id = data.get("card_photo_id")
    phone = data.get("phone", "نامشخص")
    request_id = await db.create_charge_request(message.from_user.id, amount)
    await state.clear()

    await message.answer(
        f"✅ درخواست شارژ شما ثبت شد.\n"
        f"شماره پیگیری: <code>{request_id}</code>\n"
        "بعد از تایید ادمین، موجودی حسابت اضافه میشه."
    )

    target_chat = config.CHARGE_CHANNEL_ID if config.CHARGE_CHANNEL_ID else config.ADMIN_ID
    if target_chat:
        media = [
            InputMediaPhoto(media=card_photo_id, caption="📸 عکس کارت واریزی"),
            InputMediaPhoto(media=message.photo[-1].file_id, caption="🧾 رسید واریز"),
        ]
        await bot.send_media_group(target_chat, media=media)
        await bot.send_message(
            target_chat,
            f"🆕 درخواست شارژ جدید\n"
            f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
            f"📱 شماره تلفن: {phone}\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"شماره پیگیری: {request_id}",
            reply_markup=kb.admin_charge_actions(request_id)
        )


@router.message(ChargeState.waiting_receipt)
async def receive_charge_receipt_wrong(message: Message):
    await message.answer("لطفاً عکس رسید واریزی رو ارسال کن 📸")


# ---------------- احراز هویت برای واریزهای بالای سقف روزانه ----------------
@router.message(KycState.waiting_card_photo, F.photo)
async def kyc_receive_card_photo(message: Message, state: FSMContext):
    await state.update_data(card_photo_id=message.photo[-1].file_id)
    await state.set_state(KycState.waiting_id_photo)
    await message.answer("2️⃣ حالا عکس شناسنامه (یا کارت ملی) دارنده‌ی کارت رو بفرست:")


@router.message(KycState.waiting_card_photo)
async def kyc_card_photo_wrong(message: Message):
    await message.answer("لطفاً عکس کارت رو ارسال کن 📸")


@router.message(KycState.waiting_id_photo, F.photo)
async def kyc_receive_id_photo(message: Message, state: FSMContext):
    await state.update_data(id_photo_id=message.photo[-1].file_id)
    await state.set_state(KycState.waiting_video)
    await message.answer(
        "3️⃣ حالا یه ویدیوی کوتاه از همون فرد بفرست، در حالی که می‌گه:\n"
        "«بنده در حال خرید از فروشگاه داگ استارز هستم»"
    )


@router.message(KycState.waiting_id_photo)
async def kyc_id_photo_wrong(message: Message):
    await message.answer("لطفاً عکس شناسنامه/کارت ملی رو ارسال کن 📸")


@router.message(KycState.waiting_video, F.video)
async def kyc_receive_video(message: Message, state: FSMContext):
    await state.update_data(video_id=message.video.file_id)
    await state.set_state(KycState.waiting_receipt)
    text = (
        f"✅ مدارک احراز هویت دریافت شد.\n\n"
        f"حالا مبلغ رو به شماره کارت زیر واریز کن و عکس رسیدش رو بفرست:\n\n"
        f"💳 <code>{config.CARD_NUMBER}</code>\n"
        f"👤 به نام: {config.CARD_HOLDER}\n\n"
        "📸 عکس رسید واریزی:"
    )
    await message.answer(text)


@router.message(KycState.waiting_video)
async def kyc_video_wrong(message: Message):
    await message.answer("لطفاً یه ویدیو ارسال کن 🎥")


@router.message(KycState.waiting_receipt, F.photo)
async def kyc_receive_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    card_photo_id = data.get("card_photo_id")
    id_photo_id = data.get("id_photo_id")
    video_id = data.get("video_id")
    request_id = await db.create_charge_request(message.from_user.id, amount)
    await state.clear()

    await message.answer(
        f"✅ درخواست شارژ و احراز هویت شما ثبت شد.\n"
        f"شماره پیگیری: <code>{request_id}</code>\n"
        "بعد از بررسی و تایید ادمین، موجودی حسابت اضافه میشه."
    )

    target_chat = config.KYC_CHANNEL_ID if config.KYC_CHANNEL_ID else config.ADMIN_ID
    if target_chat:
        media = [
            InputMediaPhoto(media=card_photo_id, caption="📸 عکس کارت واریزی"),
            InputMediaPhoto(media=id_photo_id, caption="🪪 عکس شناسنامه/کارت ملی"),
            InputMediaVideo(media=video_id, caption="🎥 ویدیوی احراز هویت"),
            InputMediaPhoto(media=message.photo[-1].file_id, caption="🧾 رسید واریز"),
        ]
        await bot.send_media_group(target_chat, media=media)
        await bot.send_message(
            target_chat,
            f"🆕 درخواست احراز هویت + شارژ (بالای سقف روزانه)\n"
            f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"شماره پیگیری: {request_id}\n\n"
            "⚠️ لطفاً مدارک بالا رو با دقت بررسی کن.",
            reply_markup=kb.admin_charge_actions(request_id)
        )


@router.message(KycState.waiting_receipt)
async def kyc_receipt_wrong(message: Message):
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
        try:
            await call.message.edit_text(call.message.text + "\n\n✅ تایید شد و موجودی اضافه شد.")
        except Exception:
            pass
        await bot.send_message(user_id, f"✅ شارژ حساب شما به مبلغ {amount:,} تومان تایید شد.")
    else:
        await db.set_charge_status(request_id, "rejected")
        try:
            await call.message.edit_text(call.message.text + "\n\n❌ رد شد.")
        except Exception:
            pass
        await bot.send_message(user_id, "❌ متاسفانه درخواست شارژ شما تایید نشد. با پشتیبانی در ارتباط باش.")

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


# ---------------- مدیریت متن‌های ربات (فقط ادمین) ----------------
@router.callback_query(F.data == "admin_texts")
async def cb_admin_texts(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "📝 <b>مدیریت متن‌های ربات</b>\nهر پیامی که می‌خوای ویرایش کنی رو انتخاب کن:",
        reply_markup=kb.admin_texts_menu(TEXT_LABELS)
    )
    await call.answer()


@router.callback_query(F.data.startswith("admintext_"))
async def cb_admin_text_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    key = call.data.replace("admintext_", "")
    current = await get_text(key)
    label = TEXT_LABELS.get(key, key)
    text = f"{label}\n\n<b>متن فعلی:</b>\n\n{current}"
    await call.message.edit_text(text, reply_markup=kb.admin_text_view_actions(key))
    await call.answer()


@router.callback_query(F.data.startswith("admintextedit_"))
async def cb_admin_text_edit_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    key = call.data.replace("admintextedit_", "")
    await state.update_data(text_key=key)
    await state.set_state(AdminState.waiting_new_text)
    await call.message.edit_text(
        "✏️ متن جدید رو بفرست.\n\n"
        "می‌تونی از تگ‌های HTML مثل &lt;b&gt;پررنگ&lt;/b&gt; هم استفاده کنی."
    )
    await call.answer()


@router.message(AdminState.waiting_new_text)
async def admin_receive_new_text(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("لطفاً یه متن معتبر بفرست.")
        return
    data = await state.get_data()
    key = data.get("text_key")
    await db.set_setting(f"text_{key}", message.text)
    await state.clear()

    label = TEXT_LABELS.get(key, key)
    await message.answer(
        f"✅ {label} با موفقیت به‌روزرسانی شد.",
        reply_markup=kb.admin_text_view_actions(key)
    )


@router.callback_query(F.data.startswith("admintextreset_"))
async def cb_admin_text_reset(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    key = call.data.replace("admintextreset_", "")
    default_text = TEXT_DEFAULTS.get(key, "")
    await db.set_setting(f"text_{key}", default_text)
    label = TEXT_LABELS.get(key, key)
    await call.message.edit_text(
        f"♻️ {label} به حالت پیش‌فرض برگشت.\n\n<b>متن فعلی:</b>\n\n{default_text}",
        reply_markup=kb.admin_text_view_actions(key)
    )
    await call.answer("بازگردانی شد ✅")


@router.callback_query(F.data.startswith("admincat_"))
async def cb_admin_category(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    category = call.data.replace("admincat_", "")
    products = await db.get_products(category)
    label = kb.CATEGORY_LABELS.get(category, category)
    text = f"📋 <b>مدیریت {label}</b>\nروی هر آیتم بزن تا ویرایش/حذفش کنی، یا آیتم جدید اضافه کن."
    if category == "stars":
        unit_price = int(await db.get_setting("stars_unit_price", DEFAULT_STARS_UNIT_PRICE))
        text += f"\n\n💱 قیمت فعلی هر استارز (تعداد دلخواه): <b>{unit_price:,}</b> تومان"
    if not products:
        text += "\n\nهنوز آیتمی اضافه نشده."
    await call.message.edit_text(text, reply_markup=kb.admin_category_menu(category, products))
    await call.answer()


@router.callback_query(F.data == "adminstarsunitprice")
async def cb_admin_stars_unit_price_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_stars_unit_price)
    await call.message.edit_text("💱 قیمت جدید هر استارز رو به تومان بفرست (فقط عدد، مثلاً 450):")
    await call.answer()


@router.message(AdminState.waiting_stars_unit_price)
async def admin_receive_stars_unit_price(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست (مثلاً 450).")
        return
    new_price = int(message.text.strip())
    await db.set_setting("stars_unit_price", new_price)
    await state.clear()

    products = await db.get_products("stars")
    await message.answer(
        f"✅ قیمت هر استارز به {new_price:,} تومان تغییر کرد.",
        reply_markup=kb.admin_category_menu("stars", products)
    )


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
