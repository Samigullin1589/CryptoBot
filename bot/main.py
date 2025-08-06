# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - АВГУСТ 2025)
# Описание: Финальная, отказоустойчивая точка входа в приложение.
# ИСПРАВЛЕНИЕ: Устранена ошибка AttributeError при подключении к Redis.
# Используется str(settings.REDIS_URL) вместо get_secret_value().
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
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота успешно установлены.")


async def on_startup(bot: Bot, deps: Deps):
    """Выполняет действия при старте бота."""
    logger.info("Запуск процедур on_startup...")
    await set_bot_commands(bot)

    setup_jobs(deps.scheduler, deps)
    deps.scheduler.start()
    logger.info("Планировщик задач запущен.")

    await deps.coin_list_service.update_coin_list()
    logger.info("Первоначальные данные успешно загружены.")
    
    if deps.admin_service:
        await deps.admin_service.notify_admins("✅ Бот успешно запущен!")


async def on_shutdown(deps: Deps):
    """Выполняет действия при остановке бота."""
    logger.info("Запуск процедур on_shutdown...")
    
    if deps.admin_service:
        await deps.admin_service.notify_admins("❗️ Бот останавливается!")

    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=False)
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
    setup_logging(level=settings.log_level)
    
    # ИСПРАВЛЕНО: Для типа RedisDsn используется str(), а не get_secret_value()
    redis_pool = redis.from_url(
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True
    )
    storage = RedisStorage(redis=redis_pool)

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")
    dp = Dispatcher(storage=storage)

    dp.include_router(admin_router)
    dp.include_router(public_router)
    logger.info("Роутеры успешно подключены.")

    async with ClientSession() as http_session:
        # В вашем файле dependencies.py нет зависимости от bot, поэтому убираем ее из build
        # Если она нужна, ее нужно добавить в метод build в dependencies.py
        deps = Deps.build(
            settings=settings, 
            http_session=http_session, 
            redis_pool=redis_pool
            # bot=bot # Раскомментируйте, если добавите bot в Deps.build
        )

        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        # В вашем файле dependencies.py нет user_service, поэтому middleware пока отключен
        # dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        logger.info("Middleware успешно зарегистрированы.")
        
        dp.startup.register(lambda: on_startup(bot, deps))
        dp.shutdown.register(lambda: on_shutdown(deps))

        logger.info("Запуск процесса опроса Telegram...")
        try:
            # Передаем deps в виде kwargs, чтобы aiogram мог внедрить их в хэндлеры
            await dp.start_polling(bot, **deps.model_dump())
        finally:
            await on_shutdown(deps)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)

