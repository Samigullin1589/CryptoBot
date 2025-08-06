# bot/main.py
# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Финальная версия главного файла.
# ИСПРАВЛЕНИЕ: Исправлен импорт и вызов функции настройки планировщика.
# =================================================================================

import asyncio
import logging

import redis.asyncio as redis
from aiohttp import ClientSession
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.settings import settings
from bot.handlers.admin.admin_menu import admin_router
from bot.handlers.public.common_handler import public_router
# ИСПРАВЛЕНО: Импортируем правильную функцию 'setup_jobs'
from bot.jobs.scheduled_tasks import setup_jobs
from bot.middlewares.activity_middleware import UserActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.utils.dependencies import Deps
from bot.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Устанавливает команды, видимые пользователям в меню Telegram."""
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="price", description="📈 Узнать курс криптовалюты"),
        BotCommand(command="market", description="📊 Обзор рынка"),
        BotCommand(command="news", description="📰 Последние новости"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота установлены.")


async def on_startup(bot: Bot, deps: Deps):
    """Действия при старте бота."""
    logger.info("Бот запускается...")
    await set_bot_commands(bot)

    # Настройка и запуск планировщика задач
    # ИСПРАВЛЕНО: Вызываем правильную функцию и передаем нужные зависимости
    setup_jobs(deps.scheduler, deps.coin_list_service)
    deps.scheduler.start()
    logger.info("Планировщик запущен.")

    # Принудительное обновление списка монет при старте
    await deps.coin_list_service.update_coin_list()
    logger.info("Данные успешно загружены при старте.")


async def on_shutdown(deps: Deps):
    """Действия при остановке бота."""
    logger.info("Бот останавливается...")
    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=True)
        logger.info("Планировщик остановлен.")

    if deps.redis_pool:
        await deps.redis_pool.close()
        logger.info("Соединение с Redis закрыто.")

    if deps.http_session and not deps.http_session.closed:
        await deps.http_session.close()
        logger.info("Сессия AIOHTTP закрыта.")
    logger.info("Бот успешно остановлен.")


async def main():
    """Главная точка входа для приложения бота."""
    setup_logging()
    
    redis_pool = redis.from_url(
        settings.REDIS_URL.get_secret_value(),
        encoding="utf-8",
        decode_responses=True
    )
    storage = RedisStorage(redis=redis_pool)

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    dp.update.middleware(ThrottlingMiddleware(rate_limit=settings.throttling.rate_limit, redis_pool=redis_pool))
    dp.update.middleware(UserActivityMiddleware(redis_pool=redis_pool))

    dp.include_router(admin_router)
    dp.include_router(public_router)
    logger.info("Роутеры подключены.")

    async with ClientSession() as http_session:
        deps = Deps.build(settings=settings, http_session=http_session, redis_pool=redis_pool)

        dp.startup.register(lambda bot_instance: on_startup(bot_instance, deps))
        dp.shutdown.register(lambda: on_shutdown(deps))

        logger.info("Запуск бота...")
        await dp.start_polling(bot, **deps.model_dump())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка. Бот остановлен: {e}", exc_info=True)

