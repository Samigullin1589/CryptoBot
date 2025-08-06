# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - АВГУСТ 2025)
# Описание: Финальная, отказоустойчивая точка входа в приложение.
# ИСПРАВЛЕНИЕ: Унифицирован вызов Deps.build с передачей bot.
# Вся инициализация происходит в строгом и логичном порядке.
# =================================================================================

import asyncio
import logging

import redis.asyncio as redis
from aiohttp import ClientSession
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

# Импортируем единый экземпляр настроек
from bot.config.settings import settings
from bot.handlers.admin.admin_menu import admin_router
from bot.handlers.public.common_handler import public_router
from bot.jobs.scheduled_tasks import setup_jobs
from bot.middlewares.activity_middleware import ActivityMiddleware
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
        # Добавьте другие команды по необходимости
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота успешно установлены.")

async def on_startup(bot: Bot, deps: Deps):
    """Выполняет действия при старте бота."""
    logger.info("Запуск процедур on_startup...")
    await set_bot_commands(bot)

    # Передаем deps в планировщик
    setup_jobs(deps.scheduler, deps)
    deps.scheduler.start()
    logger.info("Планировщик задач запущен.")

    # Выполняем первоначальную загрузку данных
    # Например, списка монет, чтобы бот был готов к работе сразу
    await deps.coin_list_service.update_coin_list()
    logger.info("Первоначальные данные успешно загружены.")
    
    # Отправка сообщения администратору о запуске
    await deps.admin_service.notify_admins("✅ Бот успешно запущен!")

async def on_shutdown(deps: Deps):
    """Выполняет действия при остановке бота."""
    logger.info("Запуск процедур on_shutdown...")
    
    # Отправка сообщения администратору об остановке
    await deps.admin_service.notify_admins("❗️ Бот останавливается!")

    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=False) # Не ждем завершения задач при быстрой остановке
        logger.info("Планировщик задач остановлен.")

    if deps.redis_pool:
        await deps.redis_pool.close()
        logger.info("Соединение с Redis закрыто.")

    if deps.http_session and not deps.http_session.closed:
        await deps.http_session.close()
        logger.info("Сессия AIOHTTP закрыта.")
    logger.info("Бот успешно остановлен.")

async def main():
    """Главная точка входа для приложения бота."""
    # 1. Настройка логирования
    setup_logging(level=settings.log_level)
    
    # 2. Инициализация хранилища FSM
    redis_pool = redis.from_url(
        settings.REDIS_URL.get_secret_value(),
        encoding="utf-8",
        decode_responses=True
    )
    storage = RedisStorage(redis=redis_pool)

    # 3. Инициализация бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    # 4. Подключение роутеров
    dp.include_router(admin_router)
    dp.include_router(public_router)
    logger.info("Роутеры успешно подключены.")

    # 5. Создание зависимостей и регистрация middleware
    async with ClientSession() as http_session:
        # Сначала создаем все зависимости, передавая им базовые ресурсы и bot
        deps = Deps.build(
            settings=settings, 
            http_session=http_session, 
            redis_pool=redis_pool, 
            bot=bot
        )

        # Теперь регистрируем middleware, передавая им нужные сервисы из deps
        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        logger.info("Middleware успешно зарегистрированы.")
        
        # 6. Регистрация хуков startup/shutdown
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        logger.info("Запуск процесса опроса Telegram...")
        # 7. Запуск бота с передачей всех зависимостей в хэндлеры
        try:
            await dp.start_polling(bot, **deps.model_dump())
        finally:
            # Гарантируем, что ресурсы будут освобождены даже при ошибке
            await on_shutdown(deps)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        # Логирование критических ошибок на верхнем уровне
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)
