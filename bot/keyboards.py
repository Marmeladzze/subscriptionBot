# keyboards.py
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import database as db

def get_cancel_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="💳 Оплата")
    builder.button(text="ℹ️ Информация")
    builder.button(text="👤 Мой профиль")
    builder.button(text="💬 Поддержка")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

async def get_payment_menu():
    builder = InlineKeyboardBuilder()
    tariffs = await db.get_all_tariffs()
    for tariff in tariffs:
        builder.button(text=f"{tariff[1]} - {tariff[2]} RUB ({tariff[3]} дн.)", callback_data=f"pay:{tariff[0]}")
    builder.adjust(1)
    return builder.as_markup()

# --- НОВАЯ КЛАВИАТУРА: Меню перед оплатой ---
def get_pre_payment_kb(tariff_id, promo_code=None, final_price=None):
    builder = InlineKeyboardBuilder()
    if promo_code:
        # Если промокод применен, кнопка оплаты содержит всю информацию
        payment_callback = f"final_pay:{tariff_id}:{promo_code}"
        builder.button(text=f"✔ Оплатить {final_price} RUB", callback_data=payment_callback)
    else:
        # Обычная кнопка оплаты
        payment_callback = f"final_pay:{tariff_id}:no_promo"
        builder.button(text="✔ Оплатить", callback_data=payment_callback)
        # Кнопка для ввода промокода
        builder.button(text="🎟️ Ввести промокод", callback_data=f"enter_promo:{tariff_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_panel():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Статистика")
    builder.button(text="📤 Рассылка")
    builder.button(text="⚙️ Управление тарифами")
    builder.button(text="👥 Пользователи")
    # --- НОВАЯ КНОПКА ---
    builder.button(text="🎟️ Промокоды")
    builder.button(text="🔄 Сменить канал")
    builder.button(text="🖼️ Сменить фото приветствия")
    builder.button(text="📝 Изменить текст 'О канале'")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_user_management_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Продлить подписку", callback_data=f"extend_sub:{user_id}")
    builder.button(text="🗑️ Аннулировать", callback_data=f"revoke_sub:{user_id}")
    builder.adjust(1)
    return builder.as_markup()

# --- НОВАЯ КЛАВИАТУРА: Управление промокодами ---
async def get_promo_codes_management_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать новый промокод", callback_data="create_promo")
    all_codes = await db.get_all_promo_codes()
    for code in all_codes:
        promo_id, code_text, discount, uses, max_uses, is_active = code
        status_emoji = "✅" if is_active else "❌"
        action_text = "Деактивировать" if is_active else "Активировать"
        
        button_text = f"{status_emoji} {code_text} ({discount}%) - {uses}/{max_uses} | {action_text}"
        builder.button(text=button_text, callback_data=f"toggle_promo:{promo_id}")

    builder.adjust(1)
    return builder.as_markup()

async def get_manage_tariffs_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить новый тариф", callback_data="add_tariff")
    tariffs = await db.get_all_tariffs()
    for tariff in tariffs:
        builder.button(text=f"❌ Удалить: {tariff[1]} ({tariff[2]} RUB)", callback_data=f"delete_tariff:{tariff[0]}")
    builder.adjust(1)
    return builder.as_markup()