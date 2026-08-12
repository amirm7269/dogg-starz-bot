from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

CATEGORY_LABELS = {
    "stars": "استارز",
    "gift_special": "گیفت‌های مناسبتی",
    "gift_normal": "گیفت‌های عادی",
    "premium": "پرمیوم",
}

# ---------- منوی اصلی ----------
def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐️ خرید استارز", callback_data="menu_stars")
    b.button(text="🎁 خرید گیفت", callback_data="menu_gift")
    b.button(text="💎 خرید پرمیوم", callback_data="menu_premium")
    b.button(text="💳 افزایش موجودی", callback_data="menu_charge")
    b.button(text="👤 حساب من", callback_data="menu_account")
    b.button(text="🔗 زیرمجموعه‌گیری", callback_data="menu_referral")
    b.button(text="📦 سفارش‌های من", callback_data="menu_orders")
    b.button(text="🆘 پشتیبانی", callback_data="menu_support")
    if is_admin:
        b.button(text="⚙️ پنل مدیریت", callback_data="admin_panel")
        b.adjust(2, 2, 2, 2, 1)
    else:
        b.adjust(2, 2, 2, 2)
    return b.as_markup()


def back_button(target="menu_main") -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 بازگشت به منو", callback_data=target)
    return b


# ---------- زیرمنوی گیفت: انتخاب مناسبتی/عادی ----------
def gift_type_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🎊 گیفت های مناسبتی", callback_data="menu_gift_special")
    b.button(text="🧸 گیفت های عادی", callback_data="menu_gift_normal")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنوی خرید (ساخته‌شده از روی محصولات دیتابیس) ----------
def category_menu(category: str, products, back_target="menu_main", show_custom_stars=False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product_id, name, price in products:
        b.button(text=f"{name} - {price:,} تومان", callback_data=f"item_{product_id}")
    if show_custom_stars:
        b.button(text="🔢 تعداد دلخواه (حداقل 50 عدد)", callback_data="stars_custom")
    b.button(text="🔙 بازگشت", callback_data=back_target)
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنو: افزایش موجودی ----------
def charge_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 کارت به کارت", callback_data="charge_card")
    b.button(text="🌐 درگاه آنلاین (به‌زودی)", callback_data="charge_gateway")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
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


# ---------- پنل ادمین برای تایید رسید شارژ ----------
def admin_charge_actions(request_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید شارژ", callback_data=f"admincharge_ok_{request_id}")
    b.button(text="❌ رد کردن", callback_data=f"admincharge_no_{request_id}")
    b.adjust(2)
    return b.as_markup()


# ---------- پنل ادمین برای تایید سفارش ----------
def admin_order_actions(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ انجام شد", callback_data=f"adminorder_done_{order_id}")
    b.button(text="❌ رد سفارش", callback_data=f"adminorder_cancel_{order_id}")
    b.adjust(2)
    return b.as_markup()


# ---------- پنل مدیریت محصولات ----------
def admin_panel_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ مدیریت استارز", callback_data="admincat_stars")
    b.button(text="🎊 مدیریت گیفت مناسبتی", callback_data="admincat_gift_special")
    b.button(text="🧸 مدیریت گیفت عادی", callback_data="admincat_gift_normal")
    b.button(text="⭐ مدیریت پرمیوم", callback_data="admincat_premium")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
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
