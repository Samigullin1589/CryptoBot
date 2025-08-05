# bot/main.py
# Главный файл приложения. Переработан для корректной инициализации
# и завершения работы, а также для использования современного
# паттерна Dependency Injection в aiogram 3.

import asyncio
import logging

import redis.asyncio as redis
from aiohttp import ClientSession
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.settings import load_settings
from bot.handlers.admin.admin_menu import admin_router
from bot.handlers.public.common_handler import public_router
# Важно импортировать все роутеры, которые должны работать
# from bot.handlers.game import game_router
# from bot.handlers.tools import tools_router
from bot.jobs.scheduled_tasks import setup_scheduler
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
        Bot.get_my_commands(command="market", description="📊 Обзор рынка"),
        BotCommand(command="news", description="📰 Последние новости"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота установлены.")


async def on_startup(bot: Bot, deps: Deps):
    """
    Действия при старте бота: установка команд, запуск планировщика,
    первичная загрузка данных.
    """
    logger.info("Бот запускается...")
    await set_bot_commands(bot)

    # Настройка и запуск планировщика задач
    setup_scheduler(deps)
    deps.scheduler.start()
    logger.info("Планировщик запущен.")

    # Принудительное обновление списка монет при старте для гарантии актуальности
    await deps.coin_list_service.update_coin_list()
    logger.info("Данные успешно загружены при старте.")


async def on_shutdown(deps: Deps):
    """
    Действия при остановке бота: остановка планировщика,
    закрытие соединений с Redis и HTTP сессии.
    """
    logger.info("Бот останавливается...")
    if deps.scheduler.running:
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
    """
    Главная точка входа для приложения бота.
    Инициализирует все компоненты и запускает long-polling.
    """
    setup_logging()
    settings = load_settings()

    # Инициализация пула соединений Redis и FSM хранилища
    redis_password = settings.app.redis.password.get_secret_value() if settings.app.redis.password else None
    redis_pool = redis.from_url(
        str(settings.app.redis.dsn),
        encoding="utf-8",
        decode_responses=True,
        password=redis_password
    )
    storage = RedisStorage(redis=redis_pool)

    # Инициализация бота и диспетчера
    bot = Bot(token=settings.app.bot.token.get_secret_value(), parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    # Регистрация middleware
    dp.update.middleware(ThrottlingMiddleware(rate_limit=settings.throttling.rate_limit, redis_pool=redis_pool))
    dp.update.middleware(UserActivityMiddleware(redis_pool=redis_pool))

    # Подключение роутеров
    dp.include_router(admin_router)
    dp.include_router(public_router)
    # dp.include_router(game_router)
    # dp.include_router(tools_router)
    logger.info("Роутеры подключены.")

    # Управление ресурсами через асинхронный контекстный менеджер
    async with ClientSession() as http_session:
        # Создание контейнера зависимостей
        deps = Deps.build(settings=settings, http_session=http_session, redis_pool=redis_pool)

        # Регистрация обработчиков жизненного цикла
        dp.startup.register(lambda bot_instance: on_startup(bot_instance, deps))
        dp.shutdown.register(lambda: on_shutdown(deps))

        # Запуск long-polling с передачей зависимостей в хэндлеры
        logger.info("Запуск бота...")
        await dp.start_polling(bot, **deps.model_dump())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка. Бот остановлен: {e}", exc_info=True)
