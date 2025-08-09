# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ УСИЛЕННАЯ)
# Описание: Точка входа с улучшенной процедурой завершения работы для
# предотвращения конфликтов при перезапуске на Render.
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
from bot.handlers.public import (
    common_handler, menu_handlers, price_handler, asic_handler,
    news_handler, quiz_handler, game_handler, market_info_handler,
    crypto_center_handler
)
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


# ========================== КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ==========================
async def on_shutdown(bot: Bot, deps: Deps):
# =========================================================================
    """Выполняет действия при остановке бота, гарантируя чистое закрытие ресурсов."""
    logger.info("Запуск процедур on_shutdown...")
    if hasattr(deps, 'admin_service') and deps.admin_service:
        await deps.admin_service.notify_admins("❗️ Бот останавливается!")
    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=False)
        logger.info("Планировщик задач остановлен.")
    if deps.redis_pool:
        await deps.redis_pool.aclose()
        logger.info("Пул соединений Redis закрыт.")
    # ========================== КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ==========================
    # Явно закрываем сессию бота, чтобы корректно разорвать соединение с Telegram.
    # Это помогает предотвратить ошибку "Conflict: terminated by other getUpdates request".
    await bot.session.close()
    logger.info("Сессия бота закрыта.")
    # =========================================================================
    logger.info("Бот успешно остановлен.")


async def main():
    """Главная точка входа для приложения бота."""
    setup_logging(level=settings.log_level)
    
    redis_pool = redis.from_url(str(settings.REDIS_URL), encoding="utf-8", decode_responses=True)
    storage = RedisStorage(redis=redis_pool)

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)

    # Регистрация всех роутеров
    dp.include_router(admin_router)
    dp.include_router(common_handler.router)
    dp.include_router(menu_handlers.router)
    dp.include_router(price_handler.router)
    dp.include_router(asic_handler.router)
    dp.include_router(news_handler.router)
    dp.include_router(quiz_handler.router)
    dp.include_router(game_handler.router)
    dp.include_router(market_info_handler.router)
    dp.include_router(crypto_center_handler.router)
    logger.info("Все роутеры успешно подключены.")

    async with ClientSession() as http_session:
        deps = await Deps.build(settings=settings, http_session=http_session, redis_pool=redis_pool, bot=bot)

        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        if hasattr(deps, 'user_service'):
             dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        logger.info("Middleware успешно зарегистрированы.")
        
        # Передаем bot в on_shutdown
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        await bot.delete_webhook(drop_pending_updates=True)

        logger.info("Запуск процесса опроса Telegram...")
        # Передаем deps в start_polling
        await dp.start_polling(bot, deps=deps)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)