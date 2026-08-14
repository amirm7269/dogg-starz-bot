from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

CATEGORY_LABELS = {
    "stars": "استارز",
    "gift_special": "گیفت‌های مناسبتی",
    "gift_normal": "گیفت‌های عادی",
    "premium": "پرمیوم",
}


# ---------- کیبورد ثابت پایین صفحه (کنار آیکون پیوست) ----------
def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 خرید محصول")],
            [KeyboardButton(text="💳 افزایش موجودی"), KeyboardButton(text="👤 حساب کاربری")],
            [KeyboardButton(text="🔗 زیرمجموعه‌گیری")],
            [KeyboardButton(text="🆘 پشتیبانی"), KeyboardButton(text="📦 پیگیری سفارش")],
        ],
        resize_keyboard=True
    )


# ---------- منوی اصلی ----------
def main_menu(is_admin: bool = False, custom_items=None, labels=None) -> InlineKeyboardMarkup:
    L = labels or {}
    b = InlineKeyboardBuilder()
    b.button(text=L.get("menu_products", "🛒 خرید محصول"), callback_data="menu_products")
    b.button(text=L.get("menu_charge", "💳 افزایش موجودی"), callback_data="menu_charge")
    b.button(text=L.get("menu_account", "👤 حساب من"), callback_data="menu_account")
    b.button(text=L.get("menu_referral", "🔗 زیرمجموعه‌گیری"), callback_data="menu_referral")
    b.button(text=L.get("menu_orders", "📦 سفارش‌های من"), callback_data="menu_orders")
    b.button(text=L.get("menu_support", "🆘 پشتیبانی"), callback_data="menu_support")

    sizes = [1, 2, 1, 2]

    custom_items = custom_items or []
    for item_id, title, _content in custom_items:
        b.button(text=title, callback_data=f"custom_{item_id}")
        sizes.append(1)

    if is_admin:
        b.button(text="⚙️ پنل مدیریت", callback_data="admin_panel")
        sizes.append(1)

    b.adjust(*sizes)
    return b.as_markup()


# ---------- زیرمنوی «خرید محصول» ----------
def products_menu(labels=None) -> InlineKeyboardMarkup:
    L = labels or {}
    b = InlineKeyboardBuilder()
    b.button(text=L.get("menu_stars", "⭐️ خرید استارز"), callback_data="menu_stars")
    b.button(text=L.get("menu_gift", "🎁 خرید گیفت"), callback_data="menu_gift")
    b.button(text=L.get("menu_premium", "💎 خرید پرمیوم"), callback_data="menu_premium")
    b.button(text=L.get("menu_reaction", "🎯 ری‌اکشن استارزی"), callback_data="menu_reaction")
    b.button(text=L.get("menu_ton", "🪙 خرید ارز تون"), callback_data="menu_ton")
    b.button(text="🔙 بازگشت به منو", callback_data="menu_main")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


# ---------- تایید خرید ری‌اکشن استارزی ----------
def confirm_reaction() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید و پرداخت از کیف پول", callback_data="confirmreaction_go")
    b.button(text="🔙 بازگشت", callback_data="menu_products")
    b.adjust(1)
    return b.as_markup()


# ---------- خرید ارز تون ----------
def ton_method_menu(labels=None) -> InlineKeyboardMarkup:
    L = labels or {}
    b = InlineKeyboardBuilder()
    b.button(text=L.get("ton_wallet", "💼 واریز به ولت شخصی (حداقل 0.1 TON)"), callback_data="ton_wallet")
    b.button(text=L.get("ton_telegram", "📱 شارژ مستقیم اکانت تلگرام (حداقل 1 TON)"), callback_data="ton_telegram")
    b.button(text="🔙 بازگشت", callback_data="menu_products")
    b.adjust(1)
    return b.as_markup()


def confirm_ton() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید و پرداخت از کیف پول", callback_data="confirmton_go")
    b.button(text="🔙 بازگشت", callback_data="menu_products")
    b.adjust(1)
    return b.as_markup()


def back_button(target="menu_main") -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 بازگشت به منو", callback_data=target)
    return b


# ---------- زیرمنوی حساب کاربری ----------
def account_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 کارت‌های من", callback_data="menu_mycards")
    b.button(text="🔙 بازگشت به منو", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنوی گیفت: انتخاب مناسبتی/عادی ----------
def gift_type_menu(labels=None) -> InlineKeyboardMarkup:
    L = labels or {}
    b = InlineKeyboardBuilder()
    b.button(text=L.get("menu_gift_special", "🎊 گیفت های مناسبتی"), callback_data="menu_gift_special")
    b.button(text=L.get("menu_gift_normal", "🧸 گیفت های عادی"), callback_data="menu_gift_normal")
    b.button(text="🔙 بازگشت", callback_data="menu_products")
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنوی خرید (ساخته‌شده از روی محصولات دیتابیس) ----------
def category_menu(category: str, products, back_target="menu_main", show_custom_stars=False, labels=None) -> InlineKeyboardMarkup:
    L = labels or {}
    b = InlineKeyboardBuilder()
    for product_id, name, price in products:
        b.button(text=f"{name} - {price:,} تومان", callback_data=f"item_{product_id}")
    if show_custom_stars:
        b.button(text=L.get("stars_custom", "🔢 تعداد دلخواه (حداقل 50 عدد)"), callback_data="stars_custom")
    b.button(text="🔙 بازگشت", callback_data=back_target)
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنو: افزایش موجودی ----------
def charge_menu(labels=None) -> InlineKeyboardMarkup:
    L = labels or {}
    b = InlineKeyboardBuilder()
    b.button(text=L.get("charge_card", "💳 کارت به کارت"), callback_data="charge_card")
    b.button(text=L.get("charge_gateway", "🌐 درگاه آنلاین (به‌زودی)"), callback_data="charge_gateway")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- انتخاب گیرنده: برای خودم / هدیه به دیگران ----------
def recipient_choice(product_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 برای خودم", callback_data=f"pchoice_self_{product_id}")
    b.button(text="🎁 هدیه به دیگران", callback_data=f"pchoice_gift_{product_id}")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(2, 1)
    return b.as_markup()


def recipient_choice_custom(qty: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 برای خودم", callback_data=f"cchoice_self_{qty}")
    b.button(text="🎁 هدیه به دیگران", callback_data=f"cchoice_gift_{qty}")
    b.button(text="🔙 بازگشت", callback_data="menu_stars")
    b.adjust(2, 1)
    return b.as_markup()


# ---------- تایید خرید ----------
def confirm_purchase(product_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید و پرداخت از کیف پول", callback_data=f"confirm_{product_id}")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- تایید خرید تعداد دلخواه استارز ----------
def confirm_custom_stars(qty: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید و پرداخت از کیف پول", callback_data=f"confirmcustom_{qty}")
    b.button(text="🔙 بازگشت", callback_data="menu_stars")
    b.adjust(1)
    return b.as_markup()


# ---------- انتخاب یکی از کارت‌های قبلاً تاییدشده ----------
def choose_saved_card(cards) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for card_id, card_number, _photo_id in cards:
        masked = f"{card_number[:4]}••••••••{card_number[-4:]}" if len(card_number) >= 8 else card_number
        b.button(text=f"💳 {masked}", callback_data=f"usecard_{card_id}")
    b.button(text="➕ افزودن کارت جدید (نیاز به تایید)", callback_data="addcard_new")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- پنل ادمین برای تایید رسید شارژ ----------
def admin_charge_actions(request_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید شارژ", callback_data=f"admincharge_ok_{request_id}")
    b.button(text="❌ رد کردن", callback_data=f"admincharge_no_{request_id}")
    b.adjust(2)
    return b.as_markup()


# ---------- پنل ادمین برای تایید احراز هویت ----------
def admin_kyc_actions(request_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید احراز هویت", callback_data=f"adminkyc_ok_{request_id}")
    b.button(text="❌ رد احراز هویت", callback_data=f"adminkyc_no_{request_id}")
    b.adjust(2)
    return b.as_markup()


# ---------- پنل ادمین برای تایید سفارش ----------
def admin_order_actions(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ انجام شد", callback_data=f"adminorder_done_{order_id}")
    b.button(text="❌ رد سفارش", callback_data=f"adminorder_cancel_{order_id}")
    b.adjust(2)
    return b.as_markup()


# ---------- دکمه‌ی خرید از ربات (زیر پیام‌های گزارش عمومی) ----------
def report_buy_button(bot_username: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛒 خرید از ربات", url=f"https://t.me/{bot_username}")
    b.adjust(1)
    return b.as_markup()


# ---------- عضویت اجباری در کانال‌ها ----------
def force_join_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 عضویت در کانال داگ استارز", url="https://t.me/doggStarz")
    b.button(text="📋 عضویت در کانال گزارش خرید", url="https://t.me/doggstarzReport")
    b.button(text="✅ عضو شدم", callback_data="checkjoin")
    b.adjust(1)
    return b.as_markup()


# ---------- پنل مدیریت محصولات ----------
def admin_panel_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ مدیریت استارز", callback_data="admincat_stars")
    b.button(text="🎊 مدیریت گیفت مناسبتی", callback_data="admincat_gift_special")
    b.button(text="🧸 مدیریت گیفت عادی", callback_data="admincat_gift_normal")
    b.button(text="⭐ مدیریت پرمیوم", callback_data="admincat_premium")
    b.button(text="🎯 قیمت ری‌اکشن استارزی", callback_data="admin_reaction_price")
    b.button(text="🪙 قیمت ارز تون", callback_data="admin_ton_price")
    b.button(text="📝 مدیریت متن‌های ربات", callback_data="admin_texts")
    b.button(text="🔤 مدیریت اسم دکمه‌ها", callback_data="admin_btns")
    b.button(text="💳 تغییر شماره کارت", callback_data="admin_card")
    b.button(text="🧩 مدیریت منوی سفارشی", callback_data="adminmenu_root")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def admin_reaction_price_actions() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💱 تغییر قیمت هر ری‌اکشن", callback_data="adminreactionpriceedit")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def admin_ton_price_actions() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💱 تغییر قیمت هر TON", callback_data="admintonpriceedit")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def admin_card_actions() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ ویرایش شماره کارت و نام صاحبش", callback_data="admincardedit")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


# ---------- منوی سفارشی: نمایش برای مشتری ----------
def custom_menu_view(item_id: int, parent_id, children) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for child_id, title, _content in children:
        b.button(text=title, callback_data=f"custom_{child_id}")
    back_target = f"custom_{parent_id}" if parent_id else "menu_main"
    b.button(text="🔙 بازگشت", callback_data=back_target)
    b.adjust(1)
    return b.as_markup()


# ---------- منوی سفارشی: مدیریت از پنل ادمین ----------
def admin_menu_root(items) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for item_id, title, _content in items:
        b.button(text=title, callback_data=f"adminmenu_{item_id}")
    b.button(text="➕ افزودن دکمه اصلی جدید", callback_data="adminmenuadd_root")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def admin_menu_node(item_id: int, parent_id, children) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for child_id, title, _content in children:
        b.button(text=title, callback_data=f"adminmenu_{child_id}")
    b.button(text="➕ افزودن زیرمجموعه", callback_data=f"adminmenuadd_{item_id}")
    b.button(text="✏️ ویرایش عنوان", callback_data=f"adminmenuedittitle_{item_id}")
    b.button(text="✏️ ویرایش محتوا", callback_data=f"adminmenueditcontent_{item_id}")
    b.button(text="🗑 حذف این دکمه", callback_data=f"adminmenudel_{item_id}")
    back_target = f"adminmenu_{parent_id}" if parent_id else "adminmenu_root"
    b.button(text="🔙 بازگشت", callback_data=back_target)
    b.adjust(1)
    return b.as_markup()


def admin_menu_delete_confirm(item_id: int, parent_id) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ بله، حذف کن (زیرمجموعه‌هاشم حذف میشه)", callback_data=f"adminmenudelok_{item_id}")
    b.button(text="❌ انصراف", callback_data=f"adminmenu_{item_id}")
    b.adjust(1)
    return b.as_markup()


# ---------- مدیریت متن‌های ربات ----------
def admin_texts_menu(text_labels: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in text_labels.items():
        b.button(text=label, callback_data=f"admintext_{key}")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def admin_text_view_actions(key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ ویرایش این متن", callback_data=f"admintextedit_{key}")
    b.button(text="♻️ بازگردانی به پیش‌فرض", callback_data=f"admintextreset_{key}")
    b.button(text="🔙 بازگشت به لیست متن‌ها", callback_data="admin_texts")
    b.adjust(1)
    return b.as_markup()


# ---------- مدیریت اسم دکمه‌ها ----------
def admin_btns_menu(btn_labels: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in btn_labels.items():
        b.button(text=label, callback_data=f"adminbtn_{key}")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def admin_btn_view_actions(key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ ویرایش اسم این دکمه", callback_data=f"adminbtnedit_{key}")
    b.button(text="♻️ بازگردانی به پیش‌فرض", callback_data=f"adminbtnreset_{key}")
    b.button(text="🔙 بازگشت به لیست دکمه‌ها", callback_data="admin_btns")
    b.adjust(1)
    return b.as_markup()


def admin_category_menu(category: str, products) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product_id, name, price in products:
        b.button(text=f"✏️ {name} - {price:,} تومان", callback_data=f"adminedit_{product_id}")
    if category == "stars":
        b.button(text="💱 تغییر قیمت هر استارز (تعداد دلخواه)", callback_data="adminstarsunitprice")
    b.button(text="➕ افزودن آیتم جدید", callback_data=f"adminadd_{category}")
    b.button(text="🔙 بازگشت", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def admin_item_actions(product_id: int, category: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💰 تغییر قیمت", callback_data=f"adminprice_{product_id}")
    b.button(text="✏️ تغییر نام", callback_data=f"adminname_{product_id}")
    b.button(text="🗑 حذف آیتم", callback_data=f"admindel_{product_id}")
    b.button(text="🔙 بازگشت", callback_data=f"admincat_{category}")
    b.adjust(2, 1, 1)
    return b.as_markup()


def admin_delete_confirm(product_id: int, category: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ بله، حذف کن", callback_data=f"admindelok_{product_id}")
    b.button(text="❌ انصراف", callback_data=f"adminedit_{product_id}")
    b.adjust(2)
    return b.as_markup()
