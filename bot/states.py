# states.py
from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    # Состояния для рассылки
    broadcast_text = State()
    broadcast_photo = State()
    broadcast_confirmation = State()

    # Состояния для управления тарифами
    add_tariff_name = State()
    add_tariff_price = State()
    add_tariff_duration = State()

    # Состояния для настроек
    change_channel_id = State()
    change_welcome_photo = State()
    change_about_text = State()

    # Состояния для ручного управления пользователями
    find_user_id = State()
    add_subscription_days = State()

    # --- НОВЫЕ СОСТОЯНИЯ: Для создания промокода ---
    promo_code_text = State()
    promo_code_discount = State()
    promo_code_max_uses = State()

class SupportStates(StatesGroup):
    awaiting_question = State()

# --- НОВАЯ ГРУППА: Для процесса применения промокода пользователем ---
class UserPromoStates(StatesGroup):
    awaiting_promo_code = State()