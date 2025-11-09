# main.py
import asyncio
import logging
import sys

from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
# --- ИЗМЕНЕНИЕ ЗДЕСЬ: Импортируем новую функцию из БД ---
from database import init_db, get_expired_users, get_setting, get_users_nearing_expiry
from handlers import user_handlers, admin_handlers

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# ... (функция check_subscriptions для кика остается без изменений) ...
async def check_subscriptions(bot: Bot):
    channel_id_str = await get_setting('channel_id')
    if not channel_id_str or not channel_id_str.replace('-', '').isdigit():
        logger.warning("Не удалось запустить проверку подписок: ID канала не настроен или некорректен.")
        return
    channel_id = int(channel_id_str)
    expired_users = await get_expired_users()
    logger.info(f"Найдено {len(expired_users)} пользователей с истекшей подпиской для кика.")
    for user in expired_users:
        user_id = user[0]
        try:
            await bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
            await bot.unban_chat_member(chat_id=channel_id, user_id=user_id, only_if_banned=True)
            logger.info(f"Пользователь {user_id} был удален из канала {channel_id}.")
            try:
                await bot.send_message(user_id, "Срок вашей подписки на канал истёк. Вы можете оформить её заново в меню 'Оплата'.")
            except Exception:
                logger.warning(f"Не удалось уведомить пользователя {user_id} об окончании подписки.")
        except Exception as e:
            logger.error(f"Не удалось удалить пользователя {user_id} из канала {channel_id}: {e}")
        await asyncio.sleep(0.5)

# --- НОВАЯ ФУНКЦИЯ: Для отправки напоминаний ---
async def check_expiring_subscriptions(bot: Bot):
    """Проверяет и уведомляет пользователей о скором окончании подписки."""
    logger.info("Запуск проверки подписок, истекающих скоро...")
    # Напоминание за 3 дня
    users_3_days = await get_users_nearing_expiry(3)
    for user in users_3_days:
        user_id = user[0]
        try:
            await bot.send_message(user_id, "🔔 Напоминание: ваша подписка на канал истекает через 3 дня. Не забудьте продлить ее в меню '💳 Оплата', чтобы не потерять доступ!")
            logger.info(f"Отправлено уведомление за 3 дня пользователю {user_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление за 3 дня пользователю {user_id}: {e}")
        await asyncio.sleep(0.2)
    
    # Напоминание за 1 день
    users_1_day = await get_users_nearing_expiry(1)
    for user in users_1_day:
        user_id = user[0]
        try:
            await bot.send_message(user_id, "‼️ Внимание! Ваша подписка на канал истекает завтра. Продлите ее сейчас, чтобы доступ не прервался.")
            logger.info(f"Отправлено уведомление за 1 день пользователю {user_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление за 1 день пользователю {user_id}: {e}")
        await asyncio.sleep(0.2)

async def main():
    await init_db()

    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)

    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Задача для кика (можно запускать чаще, например, раз в час)
    scheduler.add_job(check_subscriptions, 'interval', hours=1, args=(bot,))
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Добавляем новую задачу для уведомлений (запускаем раз в день) ---
    scheduler.add_job(check_expiring_subscriptions, 'cron', hour=10, minute=0, args=(bot,)) # Каждый день в 10:00
    
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при выполнении: {e}", exc_info=True)