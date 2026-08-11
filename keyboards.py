from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

CATEGORY_LABELS = {
    "stars": "استارز",
    "gift": "گیفت",
    "premium": "پرمیوم",
}

# ---------- منوی اصلی ----------
def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛒 خرید استارز", callback_data="menu_stars")
    b.button(text="🎁 خرید گیفت", callback_data="menu_gift")
    b.button(text="⭐ خرید پرمیوم", callback_data="menu_premium")
    b.button(text="💳 افزایش موجودی", callback_data="menu_charge")
    b.button(text="👤 حساب کاربری", callback_data="menu_account")
    b.button(text="🔗 زیرمجموعه‌گیری", callback_data="menu_referral")
    b.button(text="📦 پیگیری سفارش", callback_data="menu_orders")
    b.button(text="🆘 پشتیبانی", callback_data="menu_support")
    if is_admin:
        b.button(text="⚙️ پنل مدیریت", callback_data="admin_panel")
        b.adjust(2, 2, 2, 2, 1)
    else:
        b.adjust(2, 2, 2, 2)
    return b.as_markup()


def back_button(target="menu_main") -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 بازگشت", callback_data=target)
    return b


# ---------- زیرمنوی خرید (ساخته‌شده از روی محصولات دیتابیس) ----------
def category_menu(category: str, products) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product_id, name, price in products:
        b.button(text=f"{name} - {price:,} تومان", callback_data=f"item_{product_id}")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
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
    b.button(text="🎁 مدیریت گیفت", callback_data="admincat_gift")
    b.button(text="⭐ مدیریت پرمیوم", callback_data="admincat_premium")
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def admin_category_menu(category: str, products) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product_id, name, price in products:
        b.button(text=f"✏️ {name} - {price:,} تومان", callback_data=f"adminedit_{product_id}")
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
