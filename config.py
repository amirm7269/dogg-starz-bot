import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# آیدی عددی چنلی که رسیدهای واریزی توش برای تایید/رد ارسال میشن (اختیاری)
# اگه ست نشه، رسیدها مثل قبل مستقیم برای ادمین پیام میشن
CHARGE_CHANNEL_ID = int(os.getenv("CHARGE_CHANNEL_ID", "0"))

# اطلاعات کارت به کارت (بعداً از داخل ربات هم می‌شه با پنل ادمین عوضش کرد)
CARD_NUMBER = os.getenv("CARD_NUMBER", "0000-0000-0000-0000")
CARD_HOLDER = os.getenv("CARD_HOLDER", "نام صاحب کارت")

DB_PATH = os.getenv("DB_PATH", "shop.db")
