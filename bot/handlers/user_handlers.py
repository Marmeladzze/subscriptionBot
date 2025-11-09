# handlers/user_handlers.py
import time
import logging
import math
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment

import database as db
import keyboards as kb
from config import PAYMENT_PROVIDER_TOKEN, ADMIN_IDS
from states import SupportStates, UserPromoStates

router = Router()
logger = logging.getLogger(__name__)

# --- ОБРАБОТКА ОСНОВНЫХ КОМАНД И КНОПОК МЕНЮ ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username)
    
    welcome_photo_id = await db.get_setting('welcome_photo_id')
    about_text = await db.get_setting('about_text')

    if welcome_photo_id:
        try:
            await message.answer_photo(
                photo=welcome_photo_id,
                caption=f"👋 Добро пожаловать!\n\n{about_text}",
                reply_markup=kb.get_main_menu()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке приветственного фото пользователю {message.from_user.id}: {e}")
            await message.answer(f"👋 Добро пожаловать!\n\n{about_text}", reply_markup=kb.get_main_menu())
    else:
        await message.answer(f"👋 Добро пожаловать!\n\n{about_text}", reply_markup=kb.get_main_menu())


@router.message(F.text == "❌ Отмена")
async def user_cancel_handler(message: Message, state: FSMContext):
    """Обработчик кнопки отмены для пользователя."""
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=kb.get_main_menu())


@router.message(F.text == "ℹ️ Информация")
async def info_handler(message: Message):
    about_text = await db.get_setting('about_text')
    await message.answer(about_text)


@router.message(F.text == "💳 Оплата")
async def payment_handler(message: Message):
    tariffs_kb = await kb.get_payment_menu()
    if not tariffs_kb.inline_keyboard:
         await message.answer("К сожалению, на данный момент нет доступных тарифов.")
         return
    await message.answer("Выберите подходящий тариф:", reply_markup=tariffs_kb)


@router.message(F.text == "👤 Мой профиль")
async def profile_handler(message: Message):
    user_id = message.from_user.id
    subscription_end_str = await db.get_user_subscription(user_id)
    
    profile_text = f"👤 <b>Ваш профиль</b>\n\n<b>ID:</b> <code>{user_id}</code>\n"
    
    if subscription_end_str:
        end_date = datetime.strptime(subscription_end_str, "%Y-%m-%d %H:%M:%S")
        if end_date > datetime.now():
            formatted_date = end_date.strftime("%d.%m.%Y в %H:%M")
            profile_text += f"<b>Статус подписки:</b> ✅ Активна до {formatted_date}"
        else:
            profile_text += "<b>Статус подписки:</b> ❌ Неактивна"
    else:
        profile_text += "<b>Статус подписки:</b> ❌ Неактивна"

    await message.answer(profile_text, parse_mode="HTML")


# --- БЛОК СИСТЕМЫ ПОДДЕРЖКИ ---

@router.message(F.text == "💬 Поддержка")
async def support_request(message: Message, state: FSMContext):
    await state.set_state(SupportStates.awaiting_question)
    await message.answer(
        "Пожалуйста, опишите ваш вопрос или проблему одним сообщением. Мы перешлем его администратору.",
        reply_markup=kb.get_cancel_kb()
    )


@router.message(SupportStates.awaiting_question)
async def process_question(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    ticket_text = (
        f"<b>❗️ Новый вопрос в поддержку</b>\n\n"
        f"<b>От пользователя:</b> {user.full_name}\n"
        f"<b>Username:</b> @{user.username if user.username else 'не указан'}\n"
        f"<b>User ID:</b> <code>{user.id}</code>\n\n"
        f"<b>Текст вопроса:</b>\n{message.text}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, ticket_text)
        except Exception as e:
            logger.error(f"Не удалось отправить тикет админу {admin_id}: {e}")

    await message.answer(
        "✅ Спасибо! Ваш вопрос был отправлен администраторам. Они ответят вам в ближайшее время.",
        reply_markup=kb.get_main_menu()
    )
    await state.clear()


# --- БЛОК ЛОГИКИ ОПЛАТЫ С ПРОМОКОДАМИ ---

@router.callback_query(F.data.startswith("pay:"))
async def select_tariff(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.split(':')[1])
    tariff_details = await db.get_tariff_details(tariff_id)
    if not tariff_details:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    tariff_name, price, duration = tariff_details
    await state.update_data(tariff_id=tariff_id)

    text = (
        f"Вы выбрали тариф «<b>{tariff_name}</b>»\n"
        f"Срок подписки: {duration} дней\n"
        f"Стоимость: {price} RUB\n\n"
        f"Нажмите 'Оплатить' или введите промокод для получения скидки."
    )
    await callback.message.edit_text(text, reply_markup=kb.get_pre_payment_kb(tariff_id))
    await callback.answer()


@router.callback_query(F.data.startswith("enter_promo:"))
async def enter_promo_code(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserPromoStates.awaiting_promo_code)
    await callback.message.edit_text("Введите ваш промокод:", reply_markup=None)
    await callback.answer()


@router.message(UserPromoStates.awaiting_promo_code)
async def process_promo_code(message: Message, state: FSMContext):
    user_code = message.text.upper()
    data = await state.get_data()
    tariff_id = data.get('tariff_id')
    
    promo_details = await db.get_promo_code_details(user_code)
    tariff_details = await db.get_tariff_details(tariff_id)
    
    tariff_name, price, duration = tariff_details

    if promo_details and promo_details[4] and promo_details[3] < promo_details[2]:
        discount = promo_details[1]
        new_price = math.ceil(price * (1 - discount / 100))
        final_price = max(1, new_price)

        text = (
            f"✅ Промокод <code>{user_code}</code> на {discount}% успешно применен!\n\n"
            f"Тариф: «<b>{tariff_name}</b>»\n"
            f"Старая цена: <s>{price} RUB</s>\n"
            f"<b>Новая цена: {final_price} RUB</b>"
        )
        await state.clear()
        await message.answer(text, reply_markup=kb.get_pre_payment_kb(tariff_id, promo_code=user_code, final_price=final_price))
    else:
        text = "❌ Промокод недействителен или его лимит исчерпан. Попробуйте еще раз или оплатите полную стоимость."
        await state.clear()
        await message.answer(text, reply_markup=kb.get_pre_payment_kb(tariff_id))


@router.callback_query(F.data.startswith("final_pay:"))
async def create_final_invoice(callback: CallbackQuery, bot: Bot):
    try:
        _, tariff_id_str, promo_code = callback.data.split(':')
        tariff_id = int(tariff_id_str)
        
        tariff_details = await db.get_tariff_details(tariff_id)
        if not tariff_details:
            await callback.answer("Тариф не найден.", show_alert=True)
            return

        tariff_name, price, duration = tariff_details
        final_price = price

        if promo_code != 'no_promo':
            promo_details = await db.get_promo_code_details(promo_code)
            if promo_details and promo_details[4] and promo_details[3] < promo_details[2]:
                discount = promo_details[1]
                new_price = math.ceil(price * (1 - discount / 100))
                final_price = max(1, new_price)
            else:
                promo_code = 'no_promo'
        
        payload_data = f"sub:{callback.from_user.id}:{tariff_id}:{final_price}:{duration}:{promo_code}"

        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Оформление подписки «{tariff_name}»",
            description=f"Доступ к каналу на {duration} дней.",
            payload=payload_data,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=f"Подписка «{tariff_name}»", amount=final_price * 100)],
        )
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при создании финального инвойса для {callback.from_user.id}: {e}")
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot):
    try:
        telegram_payment_id = message.successful_payment.telegram_payment_charge_id
        
        _, user_id_str, tariff_id_str, price_str, duration_str, promo_code = message.successful_payment.invoice_payload.split(':')
        
        user_id = int(user_id_str)
        tariff_id = int(tariff_id_str)
        price = int(price_str)
        days = int(duration_str)

        if promo_code != 'no_promo':
            await db.increment_promo_code_use(promo_code)

        tariff_details = await db.get_tariff_details(tariff_id)
        tariff_name = tariff_details[0] if tariff_details else "Неизвестный тариф"
        
        await db.add_payment_record(user_id, tariff_name, price, days, telegram_payment_id)
        
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Используем "умную" функцию и сообщаем новую дату ---
        new_end_date = await db.update_subscription(user_id, days)
        formatted_date = new_end_date.strftime("%d.%m.%Y в %H:%M")
        
        await message.answer(
            f"✅ Оплата прошла успешно! Ваша подписка обновлена и теперь активна до <b>{formatted_date}</b>."
        )
        
        channel_id = await db.get_setting('channel_id')
        if not channel_id or not channel_id.replace('-', '').isdigit():
            logger.warning(f"Невозможно отправить ссылку пользователю {user_id}: ID канала не настроен.")
            await message.answer("Ваша подписка активирована, но произошла ошибка с отправкой ссылки. Пожалуйста, обратитесь к администратору.")
            return

        expire_date = int(time.time()) + 3600
        invite_link = await bot.create_chat_invite_link(
            chat_id=int(channel_id),
            expire_date=expire_date,
            member_limit=1,
            name=f"Для {message.from_user.id}"
        )
        await message.answer(
            f"Вот ваша уникальная ссылка для входа в канал (действует 1 час):\n{invite_link.invite_link}",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа для {message.from_user.id}: {e}")
        await message.answer("Произошла ошибка при обработке платежа. Обратитесь к администратору.")