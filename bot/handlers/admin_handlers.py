import asyncio
import re
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import AdminStates

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(F.from_user.id.in_(ADMIN_IDS))

@router.message(F.text == "🎟️ Промокоды")
async def manage_promo_codes(message: Message):
    """Показывает меню управления промокодами."""
    await message.answer("Меню управления промокодами:", reply_markup=await kb.get_promo_codes_management_kb())

@router.callback_query(F.data.startswith("toggle_promo:"))
async def toggle_promo_handler(callback: CallbackQuery):
    """Активирует/деактивирует промокод."""
    promo_id = int(callback.data.split(':')[1])
    await db.toggle_promo_code_activity(promo_id)
    await callback.answer("Статус промокода изменен.")
    # Обновляем клавиатуру, чтобы показать изменения
    await callback.message.edit_reply_markup(reply_markup=await kb.get_promo_codes_management_kb())

@router.callback_query(F.data == "create_promo")
async def create_promo_start(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс создания промокода."""
    await state.set_state(AdminStates.promo_code_text)
    await callback.message.answer("Введите текст промокода (например, SALE2025). Он будет приведен к верхнему регистру.", reply_markup=kb.get_cancel_kb())
    await callback.answer()

@router.message(AdminStates.promo_code_text)
async def process_promo_text(message: Message, state: FSMContext):
    """Обрабатывает введенный текст промокода."""
    code_text = message.text.upper()
    # Проверка, не занят ли уже такой код
    if await db.get_promo_code_details(code_text):
        await message.answer("Такой промокод уже существует. Придумайте другой.")
        return
    
    await state.update_data(promo_text=code_text)
    await state.set_state(AdminStates.promo_code_discount)
    await message.answer("Отлично. Теперь введите размер скидки в процентах (только число, например, 15):")

@router.message(AdminStates.promo_code_discount)
async def process_promo_discount(message: Message, state: FSMContext):
    """Обрабатывает размер скидки."""
    if not message.text.isdigit() or not (0 < int(message.text) <= 100):
        await message.answer("Ошибка: Скидка должна быть целым числом от 1 до 100. Попробуйте еще раз.")
        return
    
    await state.update_data(promo_discount=int(message.text))
    await state.set_state(AdminStates.promo_code_max_uses)
    await message.answer("Теперь введите максимальное количество использований (только число, например, 100):")

@router.message(AdminStates.promo_code_max_uses)
async def process_promo_max_uses(message: Message, state: FSMContext):
    """Обрабатывает лимит использований и создает промокод."""
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Ошибка: Количество использований должно быть целым положительным числом. Попробуйте еще раз.")
        return
        
    data = await state.get_data()
    code_text = data.get('promo_text')
    discount = data.get('promo_discount')
    max_uses = int(message.text)
    
    await db.create_promo_code(code_text, discount, max_uses)
    await state.clear()
    
    await message.answer(f"✅ Промокод <code>{code_text}</code> на {discount}% (лимит: {max_uses} использований) успешно создан!", reply_markup=kb.get_admin_panel())

@router.message(F.reply_to_message)
async def admin_reply_to_ticket(message: Message, bot: Bot):
    original_message = message.reply_to_message
    # Проверяем, что это ответ на тикет и в нем есть текст (а не просто фото или стикер)
    if original_message.text and "User ID:" in original_message.text:
        match = re.search(r"User ID: (\d+)", original_message.text)
        if match:
            user_id = int(match.group(1))
            response_text = f"💬 <b>Ответ от поддержки:</b>\n\n{message.text}"
            try:
                await bot.send_message(user_id, response_text)
                await message.answer("✅ Ваш ответ успешно отправлен пользователю.")
            except Exception as e:
                logger.error(f"Не удалось отправить ответ пользователю {user_id}: {e}")
                await message.answer(f"❌ Не удалось отправить ответ пользователю {user_id}. Возможно, он заблокировал бота.")
        else:
             await message.answer("Не удалось извлечь ID пользователя из сообщения.")

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать в админ-панель!", reply_markup=kb.get_admin_panel())

@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    # Добавили проверку, чтобы кнопка Отмена не срабатывала в главном меню
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=kb.get_admin_panel())

# --- ИЗМЕНЕНИЕ ЗДЕСЬ: Полностью переписанный обработчик статистики ---
@router.message(F.text == "📊 Статистика")
async def get_stats_handler(message: Message):
    # Статистика по пользователям
    total_users, active_subs = await db.get_stats()
    
    # Финансовая статистика
    today_revenue, today_sales = await db.get_sales_for_period(days=1)
    week_revenue, week_sales = await db.get_sales_for_period(days=7)
    month_revenue, month_sales = await db.get_sales_for_period(days=30)
    total_revenue, total_sales = await db.get_sales_for_period()
    
    # Самый популярный тариф
    popular_tariff = await db.get_most_popular_tariff()
    if popular_tariff:
        popular_tariff_text = f"⭐ <b>Самый популярный тариф:</b> «{popular_tariff[0]}» ({popular_tariff[1]} продаж)"
    else:
        popular_tariff_text = "⭐ <b>Самый популярный тариф:</b> Нет продаж"
        
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"<b>Пользователи:</b>\n"
        f"  - Всего: <code>{total_users}</code>\n"
        f"  - Активных подписок: <code>{active_subs}</code>\n\n"
        f"<b>Финансы:</b>\n"
        f"  - <b>За сегодня:</b> {today_revenue} RUB ({today_sales} продаж)\n"
        f"  - <b>За 7 дней:</b> {week_revenue} RUB ({week_sales} продаж)\n"
        f"  - <b>За 30 дней:</b> {month_revenue} RUB ({month_sales} продаж)\n"
        f"  - <b>За все время:</b> {total_revenue} RUB ({total_sales} продаж)\n\n"
        f"{popular_tariff_text}"
    )
    
    await message.answer(stats_text)


@router.message(F.text == "👥 Пользователи")
async def find_user_start(message: Message, state: FSMContext):
    """Начинает процесс поиска пользователя по ID."""
    await state.set_state(AdminStates.find_user_id)
    await message.answer("Введите Telegram ID пользователя для управления:", reply_markup=kb.get_cancel_kb())

@router.message(AdminStates.find_user_id)
async def find_user_process(message: Message, state: FSMContext):
    """Обрабатывает введенный ID и показывает карточку пользователя."""
    if not message.text.isdigit():
        await message.answer("Ошибка: ID пользователя должен быть числом. Попробуйте еще раз.")
        return
    
    user_id = int(message.text)
    user_data = await db.get_user_profile(user_id)
    
    if not user_data:
        await message.answer(f"Пользователь с ID <code>{user_id}</code> не найден в базе данных.", reply_markup=kb.get_admin_panel())
        await state.clear()
        return

    # Формируем "карточку" пользователя
    user_id, username, sub_end_str = user_data
    profile_text = (
        f"👤 <b>Профиль пользователя</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{username if username else 'не указан'}\n"
    )
    if sub_end_str:
        end_date = datetime.strptime(sub_end_str, "%Y-%m-%d %H:%M:%S")
        if end_date > datetime.now():
            profile_text += f"<b>Статус подписки:</b> ✅ Активна до {end_date.strftime('%d.%m.%Y %H:%M')}"
        else:
            profile_text += f"<b>Статус подписки:</b> ❌ Истекла {end_date.strftime('%d.%m.%Y %H:%M')}"
    else:
        profile_text += "<b>Статус подписки:</b> ❌ Отсутствует"

    await message.answer(
        profile_text,
        reply_markup=kb.get_user_management_kb(user_id)
    )
    await state.clear()


@router.callback_query(F.data.startswith("extend_sub:"))
async def extend_sub_start(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс продления подписки."""
    user_id = int(callback.data.split(':')[1])
    await state.update_data(user_id_to_extend=user_id) # Сохраняем ID во временные данные состояния
    await state.set_state(AdminStates.add_subscription_days)
    
    await callback.message.answer(f"Введите количество дней, на которое нужно продлить подписку для пользователя <code>{user_id}</code>:", reply_markup=kb.get_cancel_kb())
    await callback.answer()

@router.message(AdminStates.add_subscription_days)
async def extend_sub_days(message: Message, state: FSMContext):
    """Завершает процесс продления подписки."""
    if not message.text.isdigit():
        await message.answer("Ошибка: Количество дней должно быть числом. Попробуйте еще раз.")
        return
        
    days = int(message.text)
    data = await state.get_data()
    user_id = data.get('user_id_to_extend')
    
    new_end_date = await db.manually_update_subscription(user_id, days)
    
    await state.clear()
    await message.answer(
        f"✅ Подписка для пользователя <code>{user_id}</code> успешно продлена на {days} дней.\n"
        f"Новая дата окончания: {new_end_date.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=kb.get_admin_panel()
    )

@router.callback_query(F.data.startswith("revoke_sub:"))
async def revoke_sub_handler(callback: CallbackQuery):
    """Обрабатывает аннулирование подписки."""
    user_id = int(callback.data.split(':')[1])
    await db.revoke_subscription(user_id)
    await callback.answer("Подписка аннулирована!", show_alert=True)
    # Обновляем сообщение с карточкой, чтобы показать новый статус
    await callback.message.edit_text(callback.message.text + "\n\n<b>(ПОДПИСКА АННУЛИРОВАНА)</b>")

# ... (остальные админские обработчики остаются без изменений)
@router.message(F.text == "📤 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    await state.set_state(AdminStates.broadcast_text)
    await message.answer("Введите текст для рассылки:", reply_markup=kb.get_cancel_kb())
@router.message(AdminStates.broadcast_text)
async def broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(AdminStates.broadcast_photo)
    await message.answer("Теперь отправьте фото для рассылки или нажмите 'Пропустить'.", reply_markup=kb.ReplyKeyboardBuilder().button(text="Пропустить").button(text="❌ Отмена").as_markup(resize_keyboard=True))
@router.message(AdminStates.broadcast_photo)
async def broadcast_photo(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo=message.photo[-1].file_id)
    elif message.text == "Пропустить":
        await state.update_data(photo=None)
    else:
        await message.answer("Пожалуйста, отправьте фото или нажмите 'Пропустить'.")
        return
    data = await state.get_data()
    text = data.get('text')
    photo_id = data.get('photo')
    preview_text = f"<b>Предпросмотр рассылки:</b>\n\n{text}"
    await state.set_state(AdminStates.broadcast_confirmation)
    confirm_kb = kb.ReplyKeyboardBuilder().button(text="✅ Отправить всем").button(text="❌ Отмена").as_markup(resize_keyboard=True)
    if photo_id:
        await message.answer_photo(photo_id, caption=preview_text, reply_markup=confirm_kb)
    else:
        await message.answer(preview_text, reply_markup=confirm_kb)
@router.message(AdminStates.broadcast_confirmation, F.text == "✅ Отправить всем")
async def confirm_broadcast(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data.get('text')
    photo_id = data.get('photo')
    await state.clear()
    user_ids = await db.get_all_user_ids()
    await message.answer(f"Начинаю рассылку для {len(user_ids)} пользователей...", reply_markup=kb.get_admin_panel())
    success = 0
    errors = 0
    for user_id in user_ids:
        try:
            if photo_id:
                await bot.send_photo(user_id, photo_id, caption=text)
            else:
                await bot.send_message(user_id, text)
            success += 1
        except Exception:
            errors += 1
        await asyncio.sleep(0.1)
    await message.answer(f"✅ Рассылка завершена!\n\nОтправлено: {success}\nОшибок: {errors}")
@router.message(F.text == "⚙️ Управление тарифами")
async def manage_tariffs(message: Message):
    await message.answer("Выберите действие:", reply_markup=await kb.get_manage_tariffs_kb())
@router.callback_query(F.data.startswith('delete_tariff:'))
async def delete_tariff_handler(callback: CallbackQuery):
    tariff_id = int(callback.data.split(':')[1])
    await db.delete_tariff(tariff_id)
    await callback.answer("Тариф удален!")
    await callback.message.edit_reply_markup(reply_markup=await kb.get_manage_tariffs_kb())
@router.callback_query(F.data == 'add_tariff')
async def add_tariff_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_tariff_name)
    await callback.message.answer("Введите название нового тарифа:", reply_markup=kb.get_cancel_kb())
    await callback.answer()
@router.message(AdminStates.add_tariff_name)
async def add_tariff_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminStates.add_tariff_price)
    await message.answer("Отлично! Теперь введите цену тарифа (только цифры, в RUB):")
@router.message(AdminStates.add_tariff_price)
async def add_tariff_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите корректную цену (только цифры).")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AdminStates.add_tariff_duration)
    await message.answer("И последнее: введите срок действия подписки в днях (только цифры):")
@router.message(AdminStates.add_tariff_duration)
async def add_tariff_duration(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите корректный срок (только цифры).")
        return
    data = await state.get_data()
    await db.add_tariff(data['name'], data['price'], int(message.text))
    await state.clear()
    await message.answer("✅ Новый тариф успешно добавлен!", reply_markup=kb.get_admin_panel())
@router.message(F.text == "🔄 Сменить канал")
async def change_channel_start(message: Message, state: FSMContext):
    await state.set_state(AdminStates.change_channel_id)
    current_id = await db.get_setting('channel_id')
    await message.answer(f"Текущий ID канала: <code>{current_id}</code>\n\nПришлите новый ID канала.", reply_markup=kb.get_cancel_kb())
@router.message(AdminStates.change_channel_id)
async def process_change_channel(message: Message, state: FSMContext):
    try:
        new_id = int(message.text)
        await db.set_setting('channel_id', str(new_id))
        await state.clear()
        await message.answer("✅ ID канала успешно обновлен!", reply_markup=kb.get_admin_panel())
    except ValueError:
        await message.answer("Неверный формат ID. Пожалуйста, отправьте корректный числовой ID.")
@router.message(F.text == "🖼️ Сменить фото приветствия")
async def change_photo_start(message: Message, state: FSMContext):
    await state.set_state(AdminStates.change_welcome_photo)
    await message.answer("Пришлите новое фото для приветственного сообщения.", reply_markup=kb.get_cancel_kb())
@router.message(AdminStates.change_welcome_photo, F.photo)
async def process_change_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await db.set_setting('welcome_photo_id', photo_id)
    await state.clear()
    await message.answer("✅ Фото приветствия успешно обновлено!", reply_markup=kb.get_admin_panel())
@router.message(F.text == "📝 Изменить текст 'О канале'")
async def change_text_start(message: Message, state: FSMContext):
    await state.set_state(AdminStates.change_about_text)
    current_text = await db.get_setting('about_text')
    await message.answer(f"<b>Текущий текст:</b>\n\n{current_text}\n\nПришлите новый текст.", reply_markup=kb.get_cancel_kb())
@router.message(AdminStates.change_about_text)
async def process_change_text(message: Message, state: FSMContext):
    await db.set_setting('about_text', message.text)
    await state.clear()
    await message.answer("✅ Текст 'О канале' успешно обновлен!", reply_markup=kb.get_admin_panel())