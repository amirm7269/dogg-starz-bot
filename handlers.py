from aiogram import Router, F, Bot, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InputMediaPhoto, InputMediaVideo, TelegramObject
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import datetime

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


# ---------------- عضویت اجباری در کانال‌ها ----------------
FORCE_JOIN_TEXT = (
    "🚫 <b>برای استفاده از ربات باید اول عضو کانال‌های زیر بشی:</b>\n\n"
    "📢 کانال داگ استارز\n"
    "📋 کانال گزارش خریدها\n\n"
    "بعد از عضویت توی هر دو کانال، دکمه‌ی «✅ عضو شدم» رو بزن:"
)


async def _is_member_of(bot: Bot, channel: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return False


async def _check_force_join(bot: Bot, user_id: int) -> bool:
    m1 = await _is_member_of(bot, config.FORCE_JOIN_CHANNEL_1, user_id)
    m2 = await _is_member_of(bot, config.FORCE_JOIN_CHANNEL_2, user_id)
    return m1 and m2


async def _send_menu_or_join_prompt(message: Message, bot: Bot, with_reply_keyboard: bool = False):
    joined = await _check_force_join(bot, message.from_user.id)
    if joined:
        text = await get_text("welcome")
        await message.answer(text, reply_markup=await build_main_menu(message.from_user.id))
        if with_reply_keyboard:
            await message.answer(
                "🔽 برای دسترسی سریع‌تر، از منوی زیر هم می‌تونی استفاده کنی:",
                reply_markup=kb.main_reply_keyboard()
            )
    else:
        await message.answer(FORCE_JOIN_TEXT, reply_markup=kb.force_join_keyboard())


class ForceJoinMiddleware(BaseMiddleware):
    """قبل از هر پیام/دکمه (به‌جز /start و دکمه‌ی «عضو شدم») چک می‌کنه که کاربر عضو کانال‌های اجباری هست یا نه."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        bot: Bot = data.get("bot")
        user = data.get("event_from_user")

        if not bot or not user or is_admin(user.id):
            return await handler(event, data)

        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "checkjoin":
            return await handler(event, data)

        state: FSMContext = data.get("state")
        if state:
            current = await state.get_state()
            if current == PhoneState.waiting_phone.state:
                return await handler(event, data)

        if await _check_force_join(bot, user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(FORCE_JOIN_TEXT, reply_markup=kb.force_join_keyboard())
            except Exception:
                await event.message.answer(FORCE_JOIN_TEXT, reply_markup=kb.force_join_keyboard())
            await event.answer()
        elif isinstance(event, Message):
            await event.answer(FORCE_JOIN_TEXT, reply_markup=kb.force_join_keyboard())
        return


router.message.outer_middleware(ForceJoinMiddleware())
router.callback_query.outer_middleware(ForceJoinMiddleware())


@router.callback_query(F.data == "checkjoin")
async def cb_check_join(call: CallbackQuery, bot: Bot):
    if await _check_force_join(bot, call.from_user.id):
        text = await get_text("welcome")
        await call.message.edit_text(text, reply_markup=await build_main_menu(call.from_user.id))
        await call.answer("✅ عضویت تایید شد!")
        await call.message.answer(
            "🔽 برای دسترسی سریع‌تر، از منوی زیر هم می‌تونی استفاده کنی:",
            reply_markup=kb.main_reply_keyboard()
        )
    else:
        await call.answer("هنوز عضو هر دو کانال نشدی! لطفاً اول عضو بشو.", show_alert=True)


DAILY_CHARGE_LIMIT = 500_000  # سقف مجاز واریز روزانه بدون احراز هویت (تومان)

KYC_INSTRUCTIONS = (
    "⚠️ <b>مبلغی که وارد کردی بیشتر از سقف مجاز روزانه (500,000 تومان) هست.</b>\n\n"
    "برای واریزهای بالای این سقف، برای جلوگیری از کلاهبرداری، نیاز به احراز هویت داری (فقط یک‌بار، برای همیشه). "
    "لازمه دو چیز رو بفرستی:\n\n"
    "1️⃣ شماره کارتی که باهاش می‌خوای واریز کنی\n"
    "2️⃣ عکس روی همون کارت\n\n"
    "بعد از تایید ادمین، شماره کارت ما برات ارسال میشه تا واریز رو انجام بدی."
)


class PhoneState(StatesGroup):
    waiting_phone = State()


def _is_iranian_phone(phone: str) -> bool:
    if not phone:
        return False
    cleaned = phone.strip().replace(" ", "").replace("+", "")
    return cleaned.startswith("98") and len(cleaned) >= 11


def _contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 ارسال شماره تلفنم", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


class ChargeState(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()      # data: amount


class KycState(StatesGroup):
    waiting_card_number = State()  # data: amount
    waiting_card_photo = State()   # data: amount, card_number



class AdminState(StatesGroup):
    waiting_new_price = State()      # data: product_id
    waiting_new_name = State()       # data: product_id
    waiting_new_item_name = State()  # data: category
    waiting_new_item_price = State() # data: category, name
    waiting_stars_unit_price = State()
    waiting_new_text = State()       # data: text_key
    waiting_new_card_number = State()
    waiting_new_card_holder = State()  # data: card_number
    waiting_reaction_unit_price = State()


class MenuBuilderState(StatesGroup):
    waiting_new_button_title = State()    # data: parent_id
    waiting_new_button_content = State()  # data: parent_id, title
    waiting_edit_title = State()          # data: item_id
    waiting_edit_content = State()        # data: item_id


class CustomStarsState(StatesGroup):
    waiting_qty = State()


class ReactionState(StatesGroup):
    waiting_qty = State()
    waiting_post_link = State()


class GiftState(StatesGroup):
    waiting_recipient = State()  # data: kind ('product'|'custom'), ref (product_id or qty)


USERNAME_RE_ERROR = (
    "⚠️ یوزرنیم واردشده معتبر نیست. یوزرنیم تلگرام باید بین 5 تا 32 کاراکتر باشه و فقط شامل حروف، عدد و "
    "زیرخط (_) باشه. لطفاً دوباره بفرست (با یا بدون @):"
)


def _valid_username(raw: str) -> str | None:
    """یوزرنیم رو پاک‌سازی و اعتبارسنجی می‌کنه؛ اگه معتبر بود خودشو (بدون @) برمی‌گردونه، وگرنه None."""
    if not raw:
        return None
    cleaned = raw.strip().lstrip("@")
    import re
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", cleaned):
        return cleaned
    return None


DEFAULT_STARS_UNIT_PRICE = 450  # تومان به‌ازای هر استارز (پیش‌فرض، از پنل مدیریت قابل تغییره)
DEFAULT_REACTION_UNIT_PRICE = 450  # تومان به‌ازای هر ری‌اکشن استارزی (پیش‌فرض، از پنل مدیریت قابل تغییره)


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


async def get_card_info() -> tuple[str, str]:
    """شماره کارت و نام صاحب کارتی که به مشتری‌ها نشون داده میشه (قابل تغییر از پنل مدیریت)"""
    card_number = await db.get_setting("card_number", config.CARD_NUMBER)
    card_holder = await db.get_setting("card_holder", config.CARD_HOLDER)
    return card_number, card_holder


async def build_main_menu(user_id: int):
    """منوی اصلی رو با دکمه‌های ثابت + دکمه‌های اصلی سفارشی که ادمین اضافه کرده می‌سازه"""
    custom_items = await db.get_menu_items(None)
    return kb.main_menu(is_admin(user_id), custom_items)


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
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
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
    user = await db.get_user(message.from_user.id)
    phone = user[6] if user else None

    if not phone:
        await state.set_state(PhoneState.waiting_phone)
        await message.answer(
            "👋 خوش اومدی به <b>Dogg Starz</b>!\n\n"
            "قبل از شروع، فقط برای یک‌بار، لطفاً شماره تلفنت رو با دکمه‌ی زیر برامون بفرست:",
            reply_markup=_contact_keyboard()
        )
        return

    joined = await _check_force_join(bot, message.from_user.id)
    if joined:
        text = await get_text("welcome")
        await message.answer(text, reply_markup=await build_main_menu(message.from_user.id))
        await message.answer(
            "🔽 برای دسترسی سریع‌تر، از منوی زیر هم می‌تونی استفاده کنی:",
            reply_markup=kb.main_reply_keyboard()
        )
    else:
        await message.answer(FORCE_JOIN_TEXT, reply_markup=kb.force_join_keyboard())


@router.message(PhoneState.waiting_phone, F.contact)
async def receive_start_phone(message: Message, state: FSMContext, bot: Bot):
    phone = message.contact.phone_number
    if not _is_iranian_phone(phone):
        await message.answer(
            "⚠️ فقط شماره‌های ایرانی (با پیش‌شماره 98) قابل قبوله. لطفاً با یه اکانت با شماره ایرانی امتحان کن.",
            reply_markup=_contact_keyboard()
        )
        return

    await db.set_user_phone(message.from_user.id, phone)
    await state.clear()

    joined = await _check_force_join(bot, message.from_user.id)
    if joined:
        text = await get_text("welcome")
        await message.answer(text, reply_markup=await build_main_menu(message.from_user.id))
        await message.answer(
            "🔽 برای دسترسی سریع‌تر، از منوی زیر هم می‌تونی استفاده کنی:",
            reply_markup=kb.main_reply_keyboard()
        )
    else:
        await message.answer(FORCE_JOIN_TEXT, reply_markup=kb.force_join_keyboard())


@router.message(PhoneState.waiting_phone)
async def start_phone_wrong(message: Message):
    await message.answer(
        "لطفاً از دکمه‌ی «📱 ارسال شماره تلفنم» استفاده کن تا شماره‌ت ثبت بشه.",
        reply_markup=_contact_keyboard()
    )


# ---------------- دکمه‌های منوی ثابت (کنار آیکون پیوست) ----------------
@router.message(F.text == "🛒 خرید محصول")
async def reply_btn_buy(message: Message):
    text = await get_text("menu_main")
    await message.answer(text, reply_markup=await build_main_menu(message.from_user.id))


@router.message(F.text == "💳 افزایش موجودی")
async def reply_btn_charge(message: Message):
    text = await get_text("charge_menu")
    await message.answer(text, reply_markup=kb.charge_menu())


@router.message(F.text == "👤 حساب کاربری")
async def reply_btn_account(message: Message):
    user = await db.get_user(message.from_user.id)
    balance = user[2] if user else 0
    ref_count = await db.count_referrals(message.from_user.id)
    text = (
        "👤 ━━━━━━━━━━━━━━ 👤\n"
        "<b>حساب کاربری شما</b>\n"
        "👤 ━━━━━━━━━━━━━━ 👤\n\n"
        f"🆔 آیدی عددی: <code>{message.from_user.id}</code>\n"
        f"💰 موجودی کیف پول: <b>{balance:,}</b> تومان\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{ref_count}</b> نفر"
    )
    await message.answer(text, reply_markup=kb.account_menu())


@router.message(F.text == "🔗 زیرمجموعه‌گیری")
async def reply_btn_referral(message: Message, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{message.from_user.id}"
    ref_count = await db.count_referrals(message.from_user.id)
    intro = await get_text("referral_intro")
    text = (
        f"{intro}\n\n"
        f"🔗 لینک شما:\n<code>{link}</code>\n\n"
        f"👥 تعداد زیرمجموعه‌ها: <b>{ref_count}</b> نفر"
    )
    await message.answer(text, reply_markup=kb.back_button().as_markup())


@router.message(F.text == "🆘 پشتیبانی")
async def reply_btn_support(message: Message):
    text = await get_text("support")
    await message.answer(text, reply_markup=kb.back_button().as_markup())


@router.message(F.text == "📦 پیگیری سفارش")
async def reply_btn_orders(message: Message):
    orders = await db.get_user_orders(message.from_user.id)
    if not orders:
        text = await get_text("orders_empty")
    else:
        status_map = {"pending": "⏳ در حال پردازش", "done": "✅ انجام‌شده", "cancelled": "❌ لغو‌شده"}
        lines = ["📦 ━━━━━━━━━━━━━━ 📦", "<b>سفارش‌های اخیر شما</b>", "📦 ━━━━━━━━━━━━━━ 📦\n"]
        for order_id, category, item, price, status, created_at in orders:
            lines.append(f"🔸 {item} — {price:,} تومان\n{status_map.get(status, status)} | <code>{order_id}</code>\n")
        text = "\n".join(lines)
    await message.answer(text, reply_markup=kb.back_button().as_markup())


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
    await call.message.edit_text(text, reply_markup=await build_main_menu(call.from_user.id))
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

    await state.clear()
    text = (
        f"🔢 <b>{qty:,} استارز</b>\n\n"
        "این خرید برای خودته یا هدیه به یه شخص دیگه؟"
    )
    await message.answer(text, reply_markup=kb.recipient_choice_custom(qty))


@router.callback_query(F.data.startswith("cchoice_self_"))
async def cb_cchoice_self(call: CallbackQuery, state: FSMContext):
    if not _check_buyer_username(call):
        await call.answer(
            "برای ثبت سفارش باید یوزرنیم تلگرام داشته باشی. از تنظیمات تلگرام یه Username بذار و دوباره امتحان کن.",
            show_alert=True
        )
        return
    qty = int(call.data.replace("cchoice_self_", ""))
    await state.clear()
    unit_price = int(await db.get_setting("stars_unit_price", DEFAULT_STARS_UNIT_PRICE))
    total_price = qty * unit_price
    text = (
        "🧾 ━━━━━━━━━━━━━━ 🧾\n"
        f"<b>{qty:,} استارز</b>\n"
        "🧾 ━━━━━━━━━━━━━━ 🧾\n\n"
        f"💱 قیمت هر استارز: {unit_price:,} تومان\n"
        f"💰 مبلغ کل: <b>{total_price:,}</b> تومان\n\n"
        "برای تکمیل خرید، مبلغ از کیف پولت کسر میشه."
    )
    await call.message.edit_text(text, reply_markup=kb.confirm_custom_stars(qty))
    await call.answer()


@router.callback_query(F.data.startswith("cchoice_gift_"))
async def cb_cchoice_gift(call: CallbackQuery, state: FSMContext):
    if not _check_buyer_username(call):
        await call.answer(
            "برای ثبت سفارش باید یوزرنیم تلگرام داشته باشی. از تنظیمات تلگرام یه Username بذار و دوباره امتحان کن.",
            show_alert=True
        )
        return
    qty = int(call.data.replace("cchoice_gift_", ""))
    await state.update_data(kind="custom", ref=qty)
    await state.set_state(GiftState.waiting_recipient)
    await call.message.edit_text(
        "🎁 یوزرنیم شخصی که می‌خوای این هدیه رو براش ارسال کنی رو بفرست (با یا بدون @):",
        reply_markup=kb.back_button("menu_stars").as_markup()
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirmcustom_"))
async def cb_confirm_custom_stars(call: CallbackQuery, bot: Bot, state: FSMContext):
    qty = int(call.data.replace("confirmcustom_", ""))
    unit_price = int(await db.get_setting("stars_unit_price", DEFAULT_STARS_UNIT_PRICE))
    total_price = qty * unit_price

    user = await db.get_user(call.from_user.id)
    balance = user[2] if user else 0

    if balance < total_price:
        await call.answer("موجودی کافی نیست! اول حسابتو شارژ کن 💳", show_alert=True)
        return

    data = await state.get_data()
    recipient = None
    if data.get("kind") == "custom" and data.get("ref") == qty:
        recipient = data.get("recipient")
    await state.clear()

    base_name = f"{qty:,} استارز (تعداد دلخواه)"
    item_name = f"{base_name} (🎁 برای @{recipient})" if recipient else base_name

    await db.update_balance(call.from_user.id, -total_price)
    order_id = await db.create_order(call.from_user.id, "استارز", item_name, total_price)

    gift_line = f"🎁 گیرنده: @{recipient}\n" if recipient else ""
    await call.message.edit_text(
        "✅ ━━━━━━━━━━━━━━ ✅\n"
        "<b>سفارش شما با موفقیت ثبت شد!</b>\n"
        "✅ ━━━━━━━━━━━━━━ ✅\n\n"
        f"🔖 شماره سفارش: <code>{order_id}</code>\n"
        f"⭐️ آیتم: {base_name}\n"
        f"{gift_line}"
        f"💰 مبلغ: {total_price:,} تومان\n\n"
        "⏳ تیم پشتیبانی به‌زودی سفارش رو پردازش می‌کنه.",
        reply_markup=kb.back_button().as_markup()
    )
    await call.answer("سفارش ثبت شد ✅")

    order_target = config.ORDER_CHANNEL_ID if config.ORDER_CHANNEL_ID else config.ADMIN_ID
    if order_target:
        admin_gift_line = f"🎁 گیرنده‌ی هدیه: @{recipient}\n" if recipient else ""
        await bot.send_message(
            order_target,
            f"🆕 سفارش جدید (تعداد دلخواه)\n"
            f"کاربر: {call.from_user.id} (@{call.from_user.username})\n"
            f"آیتم: {base_name}\n"
            f"{admin_gift_line}"
            f"مبلغ: {total_price:,} تومان\n"
            f"شماره سفارش: {order_id}",
            reply_markup=kb.admin_order_actions(order_id)
        )


# ==================== ری‌اکشن استارزی ====================
@router.callback_query(F.data == "menu_reaction")
async def cb_menu_reaction(call: CallbackQuery, state: FSMContext):
    unit_price = int(await db.get_setting("reaction_unit_price", DEFAULT_REACTION_UNIT_PRICE))
    text = (
        "🎯 ━━━━━━━━━━━━━━ 🎯\n"
        "<b>ری‌اکشن استارزی</b>\n"
        "🎯 ━━━━━━━━━━━━━━ 🎯\n\n"
        f"💱 قیمت هر ری‌اکشن: {unit_price:,} تومان\n\n"
        "چند تا ری‌اکشن استارزی می‌خوای؟ عدد رو بفرست:"
    )
    await call.message.edit_text(text, reply_markup=kb.back_button().as_markup())
    await state.set_state(ReactionState.waiting_qty)
    await call.answer()


@router.message(ReactionState.waiting_qty)
async def receive_reaction_qty(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست (مثلاً 50).")
        return
    qty = int(message.text.strip())
    if qty < 1:
        await message.answer("لطفاً یه عدد بزرگ‌تر از صفر بفرست.")
        return

    await state.update_data(qty=qty)
    await state.set_state(ReactionState.waiting_post_link)
    await message.answer("🔗 حالا لینک پستی که می‌خوای روش ری‌اکشن بخوره رو بفرست:")


@router.message(ReactionState.waiting_post_link)
async def receive_reaction_post_link(message: Message, state: FSMContext):
    link = (message.text or "").strip()
    if not link or not (link.startswith("http") or link.startswith("t.me") or link.startswith("@")):
        await message.answer("لطفاً یه لینک معتبر از پست تلگرام بفرست (مثلاً https://t.me/channel/123):")
        return

    if not is_admin(message.from_user.id) and not message.from_user.username:
        await message.answer(
            "برای ثبت سفارش باید یوزرنیم تلگرام داشته باشی. از تنظیمات تلگرام یه Username بذار و دوباره امتحان کن."
        )
        await state.clear()
        return

    data = await state.get_data()
    qty = data.get("qty")
    unit_price = int(await db.get_setting("reaction_unit_price", DEFAULT_REACTION_UNIT_PRICE))
    total_price = qty * unit_price
    await state.update_data(link=link)

    text = (
        "🧾 ━━━━━━━━━━━━━━ 🧾\n"
        f"<b>{qty:,} ری‌اکشن استارزی</b>\n"
        "🧾 ━━━━━━━━━━━━━━ 🧾\n\n"
        f"🔗 پست: {link}\n"
        f"💱 قیمت هر ری‌اکشن: {unit_price:,} تومان\n"
        f"💰 مبلغ کل: <b>{total_price:,}</b> تومان\n\n"
        "برای تکمیل خرید، مبلغ از کیف پولت کسر میشه."
    )
    await message.answer(text, reply_markup=kb.confirm_reaction())


@router.callback_query(F.data == "confirmreaction_go")
async def cb_confirm_reaction(call: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    qty = data.get("qty")
    link = data.get("link")
    if not qty or not link:
        await call.answer("اطلاعات سفارش نامعتبره، دوباره از اول امتحان کن.", show_alert=True)
        return

    unit_price = int(await db.get_setting("reaction_unit_price", DEFAULT_REACTION_UNIT_PRICE))
    total_price = qty * unit_price

    user = await db.get_user(call.from_user.id)
    balance = user[2] if user else 0
    if balance < total_price:
        await call.answer("موجودی کافی نیست! اول حسابتو شارژ کن 💳", show_alert=True)
        return

    await state.clear()
    item_name = f"{qty:,} ری‌اکشن استارزی روی پست: {link}"

    await db.update_balance(call.from_user.id, -total_price)
    order_id = await db.create_order(call.from_user.id, "ری‌اکشن استارزی", item_name, total_price)

    await call.message.edit_text(
        "✅ ━━━━━━━━━━━━━━ ✅\n"
        "<b>سفارش شما با موفقیت ثبت شد!</b>\n"
        "✅ ━━━━━━━━━━━━━━ ✅\n\n"
        f"🔖 شماره سفارش: <code>{order_id}</code>\n"
        f"🎯 آیتم: {qty:,} ری‌اکشن استارزی\n"
        f"🔗 پست: {link}\n"
        f"💰 مبلغ: {total_price:,} تومان\n\n"
        "⏳ تیم پشتیبانی به‌زودی سفارش رو پردازش می‌کنه.",
        reply_markup=kb.back_button().as_markup()
    )
    await call.answer("سفارش ثبت شد ✅")

    reaction_target = config.REACTION_CHANNEL_ID if config.REACTION_CHANNEL_ID else config.ADMIN_ID
    if reaction_target:
        await bot.send_message(
            reaction_target,
            f"🆕 سفارش جدید — ری‌اکشن استارزی\n"
            f"کاربر: {call.from_user.id} (@{call.from_user.username})\n"
            f"تعداد: {qty:,} ری‌اکشن\n"
            f"🔗 پست: {link}\n"
            f"مبلغ: {total_price:,} تومان\n"
            f"شماره سفارش: {order_id}",
            reply_markup=kb.admin_order_actions(order_id)
        )


# ---------------- مدیریت قیمت ری‌اکشن استارزی (فقط ادمین) ----------------
@router.callback_query(F.data == "admin_reaction_price")
async def cb_admin_reaction_price(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.clear()
    unit_price = int(await db.get_setting("reaction_unit_price", DEFAULT_REACTION_UNIT_PRICE))
    text = f"🎯 قیمت فعلی هر ری‌اکشن استارزی: <b>{unit_price:,}</b> تومان"
    await call.message.edit_text(text, reply_markup=kb.admin_reaction_price_actions())
    await call.answer()


@router.callback_query(F.data == "adminreactionpriceedit")
async def cb_admin_reaction_price_edit_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_reaction_unit_price)
    await call.message.edit_text("💱 قیمت جدید هر ری‌اکشن رو به تومان بفرست (فقط عدد):")
    await call.answer()


@router.message(AdminState.waiting_reaction_unit_price)
async def admin_receive_reaction_price(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست (مثلاً 450).")
        return
    new_price = int(message.text.strip())
    await db.set_setting("reaction_unit_price", new_price)
    await state.clear()

    await message.answer(
        f"✅ قیمت هر ری‌اکشن به {new_price:,} تومان تغییر کرد.",
        reply_markup=kb.admin_reaction_price_actions()
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
        "این خرید برای خودته یا هدیه به یه شخص دیگه؟"
    )
    await call.message.edit_text(text, reply_markup=kb.recipient_choice(product_id))
    await call.answer()


def _check_buyer_username(call: CallbackQuery) -> bool:
    if not call.from_user.username:
        return False
    return True


@router.callback_query(F.data.startswith("pchoice_self_"))
async def cb_pchoice_self(call: CallbackQuery, state: FSMContext):
    if not _check_buyer_username(call):
        await call.answer(
            "برای ثبت سفارش باید یوزرنیم تلگرام داشته باشی. از تنظیمات تلگرام یه Username بذار و دوباره امتحان کن.",
            show_alert=True
        )
        return
    product_id = int(call.data.replace("pchoice_self_", ""))
    await state.clear()
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


@router.callback_query(F.data.startswith("pchoice_gift_"))
async def cb_pchoice_gift(call: CallbackQuery, state: FSMContext):
    if not _check_buyer_username(call):
        await call.answer(
            "برای ثبت سفارش باید یوزرنیم تلگرام داشته باشی. از تنظیمات تلگرام یه Username بذار و دوباره امتحان کن.",
            show_alert=True
        )
        return
    product_id = int(call.data.replace("pchoice_gift_", ""))
    product = await db.get_product(product_id)
    if not product:
        await call.answer("این آیتم دیگه موجود نیست.", show_alert=True)
        return
    await state.update_data(kind="product", ref=product_id)
    await state.set_state(GiftState.waiting_recipient)
    await call.message.edit_text(
        "🎁 یوزرنیم شخصی که می‌خوای این هدیه رو براش ارسال کنی رو بفرست (با یا بدون @):",
        reply_markup=kb.back_button("menu_main").as_markup()
    )
    await call.answer()


@router.message(GiftState.waiting_recipient)
async def receive_gift_recipient(message: Message, state: FSMContext):
    recipient = _valid_username(message.text or "")
    if not recipient:
        await message.answer(USERNAME_RE_ERROR)
        return

    if message.from_user.username and recipient.lower() == message.from_user.username.lower():
        await message.answer("نمی‌تونی خودتو به‌عنوان گیرنده‌ی هدیه انتخاب کنی. یوزرنیم یه شخص دیگه رو بفرست:")
        return

    await state.update_data(recipient=recipient)
    data = await state.get_data()
    kind = data.get("kind")

    if kind == "product":
        product_id = data.get("ref")
        product = await db.get_product(product_id)
        if not product:
            await message.answer("این آیتم دیگه موجود نیست.")
            await state.clear()
            return
        _, category, name, price = product
        text = (
            "🧾 ━━━━━━━━━━━━━━ 🧾\n"
            f"<b>{name}</b>\n"
            "🧾 ━━━━━━━━━━━━━━ 🧾\n\n"
            f"💰 قیمت: <b>{price:,}</b> تومان\n"
            f"🎁 گیرنده‌ی هدیه: @{recipient}\n\n"
            "برای تکمیل خرید، مبلغ از کیف پولت کسر میشه."
        )
        await message.answer(text, reply_markup=kb.confirm_purchase(product_id))
    else:  # custom stars
        qty = data.get("ref")
        unit_price = int(await db.get_setting("stars_unit_price", DEFAULT_STARS_UNIT_PRICE))
        total_price = qty * unit_price
        text = (
            "🧾 ━━━━━━━━━━━━━━ 🧾\n"
            f"<b>{qty:,} استارز</b>\n"
            "🧾 ━━━━━━━━━━━━━━ 🧾\n\n"
            f"💱 قیمت هر استارز: {unit_price:,} تومان\n"
            f"💰 مبلغ کل: <b>{total_price:,}</b> تومان\n"
            f"🎁 گیرنده‌ی هدیه: @{recipient}\n\n"
            "برای تکمیل خرید، مبلغ از کیف پولت کسر میشه."
        )
        await message.answer(text, reply_markup=kb.confirm_custom_stars(qty))


@router.callback_query(F.data.startswith("confirm_"))
async def cb_confirm_purchase(call: CallbackQuery, bot: Bot, state: FSMContext):
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

    data = await state.get_data()
    recipient = None
    if data.get("kind") == "product" and data.get("ref") == product_id:
        recipient = data.get("recipient")
    await state.clear()

    display_name = f"{name} (🎁 برای @{recipient})" if recipient else name

    await db.update_balance(call.from_user.id, -price)
    order_id = await db.create_order(call.from_user.id, kb.CATEGORY_LABELS.get(category, category), display_name, price)

    gift_line = f"🎁 گیرنده: @{recipient}\n" if recipient else ""
    await call.message.edit_text(
        "✅ ━━━━━━━━━━━━━━ ✅\n"
        "<b>سفارش شما با موفقیت ثبت شد!</b>\n"
        "✅ ━━━━━━━━━━━━━━ ✅\n\n"
        f"🔖 شماره سفارش: <code>{order_id}</code>\n"
        f"🎁 آیتم: {name}\n"
        f"{gift_line}"
        f"💰 مبلغ: {price:,} تومان\n\n"
        "⏳ تیم پشتیبانی به‌زودی سفارش رو پردازش می‌کنه.\n"
        "وضعیتش رو از «📦 پیگیری سفارش» چک کن.",
        reply_markup=kb.back_button().as_markup()
    )
    await call.answer("سفارش ثبت شد ✅")

    order_target = config.ORDER_CHANNEL_ID if config.ORDER_CHANNEL_ID else config.ADMIN_ID
    if order_target:
        admin_gift_line = f"🎁 گیرنده‌ی هدیه: @{recipient}\n" if recipient else ""
        await bot.send_message(
            order_target,
            f"🆕 سفارش جدید\n"
            f"کاربر: {call.from_user.id} (@{call.from_user.username})\n"
            f"آیتم: {name}\n"
            f"{admin_gift_line}"
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
    await call.message.edit_text(text, reply_markup=kb.account_menu())
    await call.answer()


@router.callback_query(F.data == "menu_mycards")
async def cb_my_cards(call: CallbackQuery):
    cards = await db.get_user_cards(call.from_user.id)
    if not cards:
        text = (
            "💳 <b>کارت‌های من</b>\n\n"
            "هنوز کارتی برای واریزهای بالای سقف روزانه تایید نکردی.\n"
            "وقتی برای اولین بار یه واریز بالای 500,000 تومان انجام بدی و احراز هویتش تایید بشه، کارتت اینجا ذخیره میشه."
        )
    else:
        lines = ["💳 <b>کارت‌های من</b>\n", "کارت‌هایی که برای واریز بالای سقف روزانه تاییدشدن:\n"]
        for card_id, card_number, _photo_id in cards:
            masked = f"{card_number[:4]}••••••••{card_number[-4:]}" if len(card_number) >= 8 else card_number
            lines.append(f"💳 {masked}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.back_button("menu_account").as_markup())
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


async def _show_card_and_ask_receipt(message: Message, amount: int, state: FSMContext):
    await state.update_data(amount=amount)
    await state.set_state(ChargeState.waiting_receipt)
    card_number, card_holder = await get_card_info()
    text = (
        f"مبلغ {amount:,} تومان رو به شماره کارت زیر واریز کن:\n\n"
        f"💳 <code>{card_number}</code>\n"
        f"👤 به نام: {card_holder}\n\n"
        "📸 حالا عکس رسید واریزی رو بفرست:"
    )
    await message.answer(text)


@router.message(ChargeState.waiting_amount)
async def receive_charge_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد مبلغ واریزی رو بفرست (مثلاً 200000).")
        return
    amount = int(message.text.strip())

    if amount <= DAILY_CHARGE_LIMIT:
        await _show_card_and_ask_receipt(message, amount, state)
        return

    # بالای سقف روزانه: چک کن قبلاً کارتی تایید شده داره یا نه
    cards = await db.get_user_cards(message.from_user.id)
    if cards:
        await state.update_data(amount=amount)
        await message.answer(
            "💳 یکی از کارت‌های قبلاً تاییدشده‌ت رو انتخاب کن، یا یه کارت جدید اضافه کن:",
            reply_markup=kb.choose_saved_card(cards)
        )
        return

    await state.update_data(amount=amount)
    await state.set_state(KycState.waiting_card_number)
    await message.answer(KYC_INSTRUCTIONS)
    await message.answer("1️⃣ لطفاً شماره کارتی که باهاش واریز می‌کنی رو بفرست (فقط عدد):")


@router.message(ChargeState.waiting_receipt, F.photo)
async def receive_charge_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    user = await db.get_user(message.from_user.id)
    phone = user[6] if user else None
    request_id = await db.create_charge_request(message.from_user.id, amount, phone=phone, kind="normal")
    await state.clear()

    await message.answer(
        f"✅ درخواست شارژ شما ثبت شد.\n"
        f"شماره پیگیری: <code>{request_id}</code>\n"
        "بعد از تایید ادمین، موجودی حسابت اضافه میشه."
    )

    target_chat = config.CHARGE_CHANNEL_ID if config.CHARGE_CHANNEL_ID else config.ADMIN_ID
    if target_chat:
        await bot.send_photo(
            target_chat,
            photo=message.photo[-1].file_id,
            caption=(
                f"🆕 درخواست شارژ جدید\n"
                f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                f"📱 شماره تلفن: {phone}\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"شماره پیگیری: {request_id}"
            ),
            reply_markup=kb.admin_charge_actions(request_id)
        )


@router.message(ChargeState.waiting_receipt)
async def receive_charge_receipt_wrong(message: Message):
    await message.answer("لطفاً عکس رسید واریزی رو ارسال کن 📸")


# ---------------- استفاده از کارت قبلاً تاییدشده (بدون نیاز به احراز هویت دوباره) ----------------
@router.callback_query(F.data.startswith("usecard_"))
async def cb_use_saved_card(call: CallbackQuery, state: FSMContext):
    card_id = int(call.data.replace("usecard_", ""))
    card = await db.get_user_card(card_id)
    if not card or card[1] != call.from_user.id:
        await call.answer("این کارت پیدا نشد.", show_alert=True)
        return

    data = await state.get_data()
    amount = data.get("amount", 0)
    if not amount:
        await call.answer("مبلغ نامعتبره، دوباره از اول امتحان کن.", show_alert=True)
        return

    await state.update_data(amount=amount)
    await state.set_state(ChargeState.waiting_receipt)
    card_number, card_holder = await get_card_info()
    text = (
        f"مبلغ {amount:,} تومان رو به شماره کارت زیر واریز کن:\n\n"
        f"💳 <code>{card_number}</code>\n"
        f"👤 به نام: {card_holder}\n\n"
        "📸 حالا عکس رسید واریزی رو بفرست:"
    )
    await call.message.edit_text(text)
    await call.answer()


@router.callback_query(F.data == "addcard_new")
async def cb_add_new_card(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    await state.update_data(amount=amount)
    await state.set_state(KycState.waiting_card_number)
    await call.message.edit_text(KYC_INSTRUCTIONS)
    await call.message.answer("1️⃣ لطفاً شماره کارتی که باهاش واریز می‌کنی رو بفرست (فقط عدد):")
    await call.answer()


# ---------------- احراز هویت برای واریزهای بالای سقف روزانه (فقط یک‌بار برای هر کارت جدید) ----------------
@router.message(KycState.waiting_card_number)
async def kyc_receive_card_number(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(" ", "").replace("-", "")
    if not raw.isdigit() or not (12 <= len(raw) <= 19):
        await message.answer("لطفاً شماره کارت رو درست و فقط به‌صورت عدد بفرست (16 رقم):")
        return
    await state.update_data(card_number=raw)
    await state.set_state(KycState.waiting_card_photo)
    await message.answer("2️⃣ حالا عکس روی همون کارت رو بفرست:")


@router.message(KycState.waiting_card_photo, F.photo)
async def kyc_receive_card_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    card_number = data.get("card_number")
    card_photo_id = message.photo[-1].file_id
    user = await db.get_user(message.from_user.id)
    phone = user[6] if user else None

    request_id = await db.create_charge_request(
        message.from_user.id, amount, phone=phone, kind="kyc", status="pending_kyc",
        card_number=card_number, card_photo_id=card_photo_id
    )
    await state.clear()

    await message.answer(
        "✅ مدارک شما ثبت شد و برای بررسی ارسال شد.\n"
        f"شماره پیگیری: <code>{request_id}</code>\n\n"
        "بعد از تایید، شماره کارت ما برات ارسال میشه تا واریز رو انجام بدی."
    )

    target_chat = config.KYC_CHANNEL_ID if config.KYC_CHANNEL_ID else config.ADMIN_ID
    if target_chat:
        await bot.send_photo(
            target_chat,
            photo=card_photo_id,
            caption=(
                f"🆕 درخواست احراز هویت (واریز بالای سقف روزانه)\n"
                f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                f"📱 شماره تلفن: {phone}\n"
                f"💳 شماره کارت: {card_number}\n"
                f"💰 مبلغ درخواستی: {amount:,} تومان\n"
                f"شماره پیگیری: {request_id}"
            ),
            reply_markup=kb.admin_kyc_actions(request_id)
        )


@router.message(KycState.waiting_card_photo)
async def kyc_card_photo_wrong(message: Message):
    await message.answer("لطفاً عکس کارت رو ارسال کن 📸")


# ---------------- دریافت رسید بعد از تایید احراز هویت (بدون نیاز به وضعیت خاص) ----------------
@router.message(F.photo)
async def receive_pending_kyc_receipt(message: Message, bot: Bot, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return  # این پیام قراره توسط هندلر state-دار دیگه‌ای مدیریت بشه

    pending = await db.get_awaiting_receipt(message.from_user.id)
    if not pending:
        return

    request_id, user_id, amount, status, phone, kind, card_number, card_photo_id = pending
    await db.set_charge_status(request_id, "pending")

    await message.answer(
        f"✅ رسید دریافت شد و برای تایید ارسال شد.\n"
        f"شماره پیگیری: <code>{request_id}</code>"
    )

    target_chat = config.CHARGE_CHANNEL_ID if config.CHARGE_CHANNEL_ID else config.ADMIN_ID
    if target_chat:
        await bot.send_photo(
            target_chat,
            photo=message.photo[-1].file_id,
            caption=(
                f"🆕 رسید واریز (بعد از احراز هویت)\n"
                f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                f"📱 شماره تلفن: {phone}\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"شماره پیگیری: {request_id}"
            ),
            reply_markup=kb.admin_charge_actions(request_id)
        )


# ---------------- اکشن‌های ادمین: تایید/رد احراز هویت ----------------
@router.callback_query(F.data.startswith("adminkyc_"))
async def cb_admin_kyc_action(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return

    action = call.data.split("_", 2)[1]
    request_id = call.data.split("_", 2)[2]
    req = await db.get_charge_request(request_id)
    if not req:
        await call.answer("درخواست پیدا نشد.", show_alert=True)
        return

    request_id, user_id, amount, status, phone, kind, card_number, card_photo_id = req
    if status != "pending_kyc":
        await call.answer("قبلاً بررسی شده.", show_alert=True)
        return

    if action == "ok":
        await db.set_kyc_verified(user_id, True)
        await db.add_user_card(user_id, card_number, card_photo_id)
        await db.set_charge_status(request_id, "awaiting_receipt")
        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ احراز هویت تایید شد.")
        except Exception:
            pass
        bot_card_number, bot_card_holder = await get_card_info()
        await bot.send_message(
            user_id,
            "✅ <b>احراز هویت شما تایید شد!</b>\n\n"
            f"حالا مبلغ {amount:,} تومان رو به شماره کارت زیر واریز کن:\n\n"
            f"💳 <code>{bot_card_number}</code>\n"
            f"👤 به نام: {bot_card_holder}\n\n"
            "📸 بعد از واریز، عکس رسید رو همینجا بفرست.\n\n"
            "🔖 این کارتت رو ذخیره کردیم؛ دفعات بعد دیگه نیازی به احراز هویت دوباره نیست، فقط از «💳 کارت‌های من» انتخابش کن."
        )
    else:
        await db.set_charge_status(request_id, "rejected")
        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ احراز هویت رد شد.")
        except Exception:
            pass
        await bot.send_message(user_id, "❌ متاسفانه احراز هویت شما تایید نشد. با پشتیبانی در ارتباط باش.")

    await call.answer()


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

    _, user_id, amount, status, phone, kind, card_number, card_photo_id = req
    if status != "pending":
        await call.answer("قبلاً بررسی شده.", show_alert=True)
        return

    async def _append_note(note):
        try:
            if call.message.photo:
                await call.message.edit_caption(caption=(call.message.caption or "") + note)
            else:
                await call.message.edit_text((call.message.text or "") + note)
        except Exception:
            pass

    if action == "ok":
        await db.update_balance(user_id, amount)
        await db.set_charge_status(request_id, "approved")
        try:
            await _append_note("\n\n✅ تایید شد و موجودی اضافه شد.")
        except Exception:
            pass
        await bot.send_message(user_id, f"✅ شارژ حساب شما به مبلغ {amount:,} تومان تایید شد.")
    else:
        await db.set_charge_status(request_id, "rejected")
        try:
            await _append_note("\n\n❌ رد شد.")
        except Exception:
            pass
        await bot.send_message(user_id, "❌ متاسفانه درخواست شارژ شما تایید نشد. با پشتیبانی در ارتباط باش.")

    await call.answer()


# ---------------- اکشن‌های ادمین: تغییر وضعیت سفارش ----------------
def _mask_user_id(user_id: int) -> str:
    s = str(user_id)
    if len(s) <= 4:
        return s
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


IRAN_TZ_OFFSET = datetime.timedelta(hours=3, minutes=30)


def _format_ir_time(iso_str: str) -> str:
    if not iso_str:
        return "-"
    try:
        dt = datetime.datetime.fromisoformat(iso_str) + IRAN_TZ_OFFSET
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    except Exception:
        return iso_str


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

    _, user_id, category, item, price, status, created_at, completed_at = order

    if action == "done":
        await db.set_order_status(order_id, "done")
        await call.message.edit_text(call.message.text + "\n\n✅ انجام شد.")
        await bot.send_message(user_id, f"✅ سفارش شما ({item}) با موفقیت انجام شد. ممنون از خریدت 🐾")

        if config.REPORTS_CHANNEL_ID:
            order_after = await db.get_order(order_id)
            completed_at_new = order_after[7] if order_after else None
            me = await bot.get_me()
            report_text = (
                "🛍 <b>گزارش خرید موفق</b>\n\n"
                f"👤 خریدار: <code>{_mask_user_id(user_id)}</code>\n"
                f"📦 سفارش: {item}\n"
                f"🏷 دسته: {category}\n"
                f"💰 مبلغ پرداخت‌شده: {price:,} تومان\n\n"
                f"🕐 ثبت سفارش: {_format_ir_time(created_at)}\n"
                f"✅ تکمیل سفارش: {_format_ir_time(completed_at_new)}\n\n"
                f"🤖 @{me.username}\n"
                "🐾 Dogg Starz | داگ استارز"
            )
            try:
                await bot.send_message(
                    config.REPORTS_CHANNEL_ID,
                    report_text,
                    reply_markup=kb.report_buy_button(me.username)
                )
            except Exception:
                pass
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


# ---------------- مدیریت شماره کارت نمایش‌داده‌شده به مشتری (فقط ادمین) ----------------
@router.callback_query(F.data == "admin_card")
async def cb_admin_card(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.clear()
    card_number, card_holder = await get_card_info()
    text = (
        "💳 <b>شماره کارت فعلی که به مشتری‌ها نشون داده میشه:</b>\n\n"
        f"شماره کارت: <code>{card_number}</code>\n"
        f"به نام: {card_holder}"
    )
    await call.message.edit_text(text, reply_markup=kb.admin_card_actions())
    await call.answer()


@router.callback_query(F.data == "admincardedit")
async def cb_admin_card_edit_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_new_card_number)
    await call.message.edit_text("💳 شماره کارت جدید رو بفرست (فقط عدد):")
    await call.answer()


@router.message(AdminState.waiting_new_card_number)
async def admin_receive_new_card_number(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(" ", "").replace("-", "")
    if not raw.isdigit() or not (12 <= len(raw) <= 19):
        await message.answer("لطفاً شماره کارت رو درست و فقط به‌صورت عدد بفرست (16 رقم):")
        return
    await state.update_data(card_number=raw)
    await state.set_state(AdminState.waiting_new_card_holder)
    await message.answer("👤 حالا نام صاحب کارت رو بفرست:")


@router.message(AdminState.waiting_new_card_holder)
async def admin_receive_new_card_holder(message: Message, state: FSMContext):
    holder = (message.text or "").strip()
    if not holder:
        await message.answer("لطفاً یه نام معتبر بفرست.")
        return
    data = await state.get_data()
    card_number = data.get("card_number")

    await db.set_setting("card_number", card_number)
    await db.set_setting("card_holder", holder)
    await state.clear()

    await message.answer(
        f"✅ شماره کارت به‌روزرسانی شد.\n\n"
        f"💳 <code>{card_number}</code>\n"
        f"👤 به نام: {holder}",
        reply_markup=kb.admin_card_actions()
    )


# ==================== منوی سفارشی: نمایش برای مشتری ====================
@router.callback_query(F.data.startswith("custom_"))
async def cb_custom_menu_item(call: CallbackQuery):
    item_id = int(call.data.replace("custom_", ""))
    item = await db.get_menu_item(item_id)
    if not item:
        await call.answer("این بخش دیگه موجود نیست.", show_alert=True)
        return

    _, parent_id, title, content = item
    children = await db.get_menu_items(item_id)

    text = f"<b>{title}</b>\n\n{content}" if content else f"<b>{title}</b>"
    await call.message.edit_text(text, reply_markup=kb.custom_menu_view(item_id, parent_id, children))
    await call.answer()


# ==================== منوی سفارشی: مدیریت از پنل ادمین ====================
@router.callback_query(F.data == "adminmenu_root")
async def cb_adminmenu_root(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.clear()
    items = await db.get_menu_items(None)
    text = "🧩 <b>مدیریت منوی سفارشی</b>\n\nدکمه‌های اصلی که خودتون به منو اضافه کردید:"
    if not items:
        text += "\n\nهنوز دکمه‌ای اضافه نکردید."
    await call.message.edit_text(text, reply_markup=kb.admin_menu_root(items))
    await call.answer()


@router.callback_query(F.data.startswith("adminmenu_"))
async def cb_adminmenu_node(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    await state.clear()
    item_id = int(call.data.replace("adminmenu_", ""))
    item = await db.get_menu_item(item_id)
    if not item:
        await call.answer("این آیتم پیدا نشد.", show_alert=True)
        return

    _, parent_id, title, content = item
    children = await db.get_menu_items(item_id)

    text = f"🧩 <b>{title}</b>\n\n"
    text += f"محتوای فعلی:\n{content}\n\n" if content else "هنوز محتوایی برای این دکمه تنظیم نشده.\n\n"
    text += "زیرمجموعه‌های این دکمه:" if children else "این دکمه هنوز زیرمجموعه‌ای نداره."
    await call.message.edit_text(text, reply_markup=kb.admin_menu_node(item_id, parent_id, children))
    await call.answer()


@router.callback_query(F.data.startswith("adminmenuadd_"))
async def cb_adminmenu_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    raw = call.data.replace("adminmenuadd_", "")
    parent_id = None if raw == "root" else int(raw)
    await state.update_data(parent_id=parent_id)
    await state.set_state(MenuBuilderState.waiting_new_button_title)
    await call.message.edit_text("✏️ عنوان دکمه‌ی جدید رو بفرست (همونی که روی دکمه نمایش داده میشه):")
    await call.answer()


@router.message(MenuBuilderState.waiting_new_button_title)
async def menu_receive_new_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("لطفاً یه عنوان معتبر بفرست.")
        return
    await state.update_data(title=title)
    await state.set_state(MenuBuilderState.waiting_new_button_content)
    await message.answer(
        "📝 حالا محتوایی که با زدن این دکمه نمایش داده میشه رو بفرست.\n\n"
        "اگه این دکمه فقط قراره چند تا زیرمجموعه داشته باشه و خودش متنی نداره، همین‌جا یه خط کوتاه (مثلاً یه توضیح ساده) بفرست."
    )


@router.message(MenuBuilderState.waiting_new_button_content)
async def menu_receive_new_content(message: Message, state: FSMContext):
    content = message.text or ""
    if not content.strip():
        await message.answer("لطفاً یه متن معتبر بفرست.")
        return
    data = await state.get_data()
    parent_id = data.get("parent_id")
    title = data.get("title")

    new_id = await db.add_menu_item(parent_id, title, content)
    await state.clear()

    await message.answer(f"✅ دکمه‌ی «{title}» اضافه شد.")

    if parent_id is None:
        items = await db.get_menu_items(None)
        await message.answer("🧩 <b>مدیریت منوی سفارشی</b>", reply_markup=kb.admin_menu_root(items))
    else:
        item = await db.get_menu_item(parent_id)
        children = await db.get_menu_items(parent_id)
        _, grandparent_id, p_title, p_content = item
        text = f"🧩 <b>{p_title}</b>\n\nزیرمجموعه‌های این دکمه:"
        await message.answer(text, reply_markup=kb.admin_menu_node(parent_id, grandparent_id, children))


@router.callback_query(F.data.startswith("adminmenuedittitle_"))
async def cb_adminmenu_edit_title_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    item_id = int(call.data.replace("adminmenuedittitle_", ""))
    await state.update_data(item_id=item_id)
    await state.set_state(MenuBuilderState.waiting_edit_title)
    await call.message.edit_text("✏️ عنوان جدید رو بفرست:")
    await call.answer()


@router.message(MenuBuilderState.waiting_edit_title)
async def menu_receive_edit_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("لطفاً یه عنوان معتبر بفرست.")
        return
    data = await state.get_data()
    item_id = data.get("item_id")
    await db.update_menu_item_title(item_id, title)
    await state.clear()

    item = await db.get_menu_item(item_id)
    _, parent_id, new_title, content = item
    children = await db.get_menu_items(item_id)
    text = f"✅ عنوان به‌روزرسانی شد.\n\n🧩 <b>{new_title}</b>"
    await message.answer(text, reply_markup=kb.admin_menu_node(item_id, parent_id, children))


@router.callback_query(F.data.startswith("adminmenueditcontent_"))
async def cb_adminmenu_edit_content_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    item_id = int(call.data.replace("adminmenueditcontent_", ""))
    await state.update_data(item_id=item_id)
    await state.set_state(MenuBuilderState.waiting_edit_content)
    await call.message.edit_text("📝 محتوای جدید رو بفرست:")
    await call.answer()


@router.message(MenuBuilderState.waiting_edit_content)
async def menu_receive_edit_content(message: Message, state: FSMContext):
    content = message.text or ""
    if not content.strip():
        await message.answer("لطفاً یه متن معتبر بفرست.")
        return
    data = await state.get_data()
    item_id = data.get("item_id")
    await db.update_menu_item_content(item_id, content)
    await state.clear()

    item = await db.get_menu_item(item_id)
    _, parent_id, title, new_content = item
    children = await db.get_menu_items(item_id)
    text = f"✅ محتوا به‌روزرسانی شد.\n\n🧩 <b>{title}</b>\n\n{new_content}"
    await message.answer(text, reply_markup=kb.admin_menu_node(item_id, parent_id, children))


@router.callback_query(F.data.startswith("adminmenudelok_"))
async def cb_adminmenu_delete_confirmed(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    item_id = int(call.data.replace("adminmenudelok_", ""))
    item = await db.get_menu_item(item_id)
    parent_id = item[1] if item else None

    await db.delete_menu_item(item_id)

    if parent_id is None:
        items = await db.get_menu_items(None)
        await call.message.edit_text(
            "🗑 دکمه حذف شد.\n\n🧩 <b>مدیریت منوی سفارشی</b>",
            reply_markup=kb.admin_menu_root(items)
        )
    else:
        parent_item = await db.get_menu_item(parent_id)
        if parent_item:
            _, grandparent_id, p_title, _ = parent_item
            children = await db.get_menu_items(parent_id)
            await call.message.edit_text(
                f"🗑 دکمه حذف شد.\n\n🧩 <b>{p_title}</b>",
                reply_markup=kb.admin_menu_node(parent_id, grandparent_id, children)
            )
    await call.answer("حذف شد ✅")


@router.callback_query(F.data.startswith("adminmenudel_"))
async def cb_adminmenu_delete_ask(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ فقط ادمین دسترسی داره.", show_alert=True)
        return
    item_id = int(call.data.replace("adminmenudel_", ""))
    item = await db.get_menu_item(item_id)
    if not item:
        await call.answer("این آیتم پیدا نشد.", show_alert=True)
        return
    _, parent_id, title, _content = item
    await call.message.edit_text(
        f"⚠️ مطمئنی می‌خوای «{title}» رو حذف کنی؟\n"
        "اگه زیرمجموعه داشته باشه، اونام حذف میشن.",
        reply_markup=kb.admin_menu_delete_confirm(item_id, parent_id)
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
