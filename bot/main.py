# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Финальная, отказоустойчивая точка входа в приложение.
# ИСПРАВЛЕНИЕ: Добавлена регистрация нового роутера для обработки цен.
# =================================================================================

import asyncio
import logging

import redis.asyncio as redis
from aiohttp import ClientSession
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.settings import settings
from bot.handlers.admin.admin_menu import admin_router
from bot.handlers.public.common_handler import public_router
# ИСПРАВЛЕНО: Импортируем новые роутеры
from bot.handlers.public.menu_handlers import router as menu_router
from bot.handlers.public.price_handler import router as price_router
from bot.jobs.scheduled_tasks import setup_jobs
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.utils.dependencies import Deps
from bot.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# ... (функции on_startup, on_shutdown, set_bot_commands без изменений) ...
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="price", description="📈 Узнать курс криптовалюты"),
        BotCommand(command="market", description="📊 Обзор рынка"),
        BotCommand(command="news", description="📰 Последние новости"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота успешно установлены.")

async def on_startup(bot: Bot, deps: Deps):
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
    logger.info("Запуск процедур on_shutdown...")
    if hasattr(deps, 'admin_service') and deps.admin_service:
        await deps.admin_service.notify_admins("❗️ Бот останавливается!")
    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=False)
        logger.info("Планировщик задач остановлен.")
    if deps.redis_pool:
        await deps.redis_pool.aclose()
        logger.info("Соединение с Redis закрыто.")
    logger.info("Бот успешно остановлен.")


async def main():
    """Главная точка входа для приложения бота."""
    setup_logging(level=settings.log_level)
    
    redis_pool = redis.from_url(str(settings.REDIS_URL), encoding="utf-8", decode_responses=True)
    storage = RedisStorage(redis=redis_pool)

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)

    # ИСПРАВЛЕНО: Подключаем все роутеры
    dp.include_router(admin_router)
    dp.include_router(public_router)
    dp.include_router(menu_router)
    dp.include_router(price_router) # <--- НОВЫЙ РОУТЕР
    logger.info("Роутеры успешно подключены.")

    async with ClientSession() as http_session:
        deps = Deps.build(settings=settings, http_session=http_session, redis_pool=redis_pool, bot=bot)

        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        if hasattr(deps, 'user_service'):
             dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        logger.info("Middleware успешно зарегистрированы.")
        
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        await bot.delete_webhook(drop_pending_updates=True)

        logger.info("Запуск процесса опроса Telegram...")
        await dp.start_polling(bot, deps=deps)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)
