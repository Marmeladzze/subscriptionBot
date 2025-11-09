# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Необходимо указать BOT_TOKEN в файле .env")

ADMIN_IDS_STR = os.getenv('ADMIN_IDS')
if not ADMIN_IDS_STR:
    raise ValueError("Необходимо указать ADMIN_IDS в файле .env")

try:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',')]
except ValueError:
    raise ValueError("ADMIN_IDS в .env файле должны быть числами, разделенными запятой")

# --- ИЗМЕНЕНИЕ ЗДЕСЬ: Возвращаемся к одному токену ---
PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN')
if not PAYMENT_PROVIDER_TOKEN:
    raise ValueError("Необходимо указать PAYMENT_PROVIDER_TOKEN в файле .env")