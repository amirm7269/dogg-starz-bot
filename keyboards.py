from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

# ---------- منوی اصلی ----------
def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛒 خرید استارز", callback_data="menu_stars")
    b.button(text="🎁 خرید گیفت", callback_data="menu_gift")
    b.button(text="⭐ خرید پرمیوم", callback_data="menu_premium")
    b.button(text="💳 افزایش موجودی", callback_data="menu_charge")
    b.button(text="👤 حساب کاربری", callback_data="menu_account")
    b.button(text="🔗 زیرمجموعه‌گیری", callback_data="menu_referral")
    b.button(text="📦 پیگیری سفارش", callback_data="menu_orders")
    b.button(text="🆘 پشتیبانی", callback_data="menu_support")
    b.adjust(2, 2, 2, 2)
    return b.as_markup()


def back_button(target="menu_main") -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 بازگشت", callback_data=target)
    return b


# ---------- زیرمنو: خرید استارز ----------
STARS_PACKAGES = {
    "stars_100": (100, 45000),
    "stars_500": (500, 210000),
    "stars_1000": (1000, 400000),
    "stars_2500": (2500, 950000),
}

def stars_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (amount, price) in STARS_PACKAGES.items():
        b.button(text=f"⭐ {amount} استارز - {price:,} تومان", callback_data=key)
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنو: خرید گیفت ----------
GIFT_ITEMS = {
    "gift_1": ("خرس تدی 🧸", 120000),
    "gift_2": ("قلب طلایی 💛", 90000),
    "gift_3": ("کیک تولد 🎂", 60000),
    "gift_4": ("راکت فضایی 🚀", 200000),
}

def gift_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (name, price) in GIFT_ITEMS.items():
        b.button(text=f"{name} - {price:,} تومان", callback_data=key)
    b.button(text="🔙 بازگشت", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


# ---------- زیرمنو: خرید پرمیوم ----------
PREMIUM_PLANS = {
    "premium_1m": ("۱ ماهه", 350000),
    "premium_3m": ("۳ ماهه", 950000),
    "premium_12m": ("۱۲ ماهه", 3200000),
}

def premium_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (label, price) in PREMIUM_PLANS.items():
        b.button(text=f"⭐ پرمیوم {label} - {price:,} تومان", callback_data=key)
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
def confirm_purchase(callback_data: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تایید و پرداخت از کیف پول", callback_data=f"confirm_{callback_data}")
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
