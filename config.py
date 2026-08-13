import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# آدرس اتصال دیتابیس PostgreSQL دائمی (خودش با اضافه کردن سرویس Postgres در Railway ست میشه)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# آیدی عددی چنلی که رسیدهای واریزی توش برای تایید/رد ارسال میشن (اختیاری)
# اگه ست نشه، رسیدها مثل قبل مستقیم برای ادمین پیام میشن
CHARGE_CHANNEL_ID = int(os.getenv("CHARGE_CHANNEL_ID", "0"))

# آیدی عددی چنلی که سفارش‌های خرید (استارز/گیفت/پرمیوم) توش برای تایید/رد ارسال میشن (اختیاری)
# اگه ست نشه، سفارش‌ها مثل قبل مستقیم برای ادمین پیام میشن
ORDER_CHANNEL_ID = int(os.getenv("ORDER_CHANNEL_ID", "0"))

# آیدی عددی چنلی که مدارک احراز هویت (برای واریزهای بالای سقف روزانه) توش ارسال میشن (اختیاری)
# اگه ست نشه، مدارک مستقیم برای ادمین پیام میشن
KYC_CHANNEL_ID = int(os.getenv("KYC_CHANNEL_ID", "0"))

# آیدی عددی چنل عمومی گزارش خریدهای موفق (برای جلب اعتماد مشتری‌های جدید) - اختیاری
# اگه ست نشه، گزارشی ارسال نمیشه
REPORTS_CHANNEL_ID = int(os.getenv("REPORTS_CHANNEL_ID", "0"))

# دو کانالی که عضویت توشون برای استفاده از ربات اجباریه
FORCE_JOIN_CHANNEL_1 = os.getenv("FORCE_JOIN_CHANNEL_1", "@doggstarzReport")
FORCE_JOIN_CHANNEL_2 = os.getenv("FORCE_JOIN_CHANNEL_2", "@doggStarz")

# اطلاعات کارت به کارت (بعداً از داخل ربات هم می‌شه با پنل ادمین عوضش کرد)
CARD_NUMBER = os.getenv("CARD_NUMBER", "0000-0000-0000-0000")
CARD_HOLDER = os.getenv("CARD_HOLDER", "نام صاحب کارت")

DB_PATH = os.getenv("DB_PATH", "shop.db")
