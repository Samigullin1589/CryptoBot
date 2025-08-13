# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ОТКАЗОУСТОЙЧИВАЯ)
# Описание: Точка входа с обработкой сигналов для Graceful Shutdown на Render.
# =================================================================================

import asyncio
import logging
import signal
from typing import Coroutine

from aiohttp import ClientSession
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.settings import settings
from bot.utils.dependencies import Deps
from bot.utils.logging_setup import setup_logging
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.jobs.scheduled_tasks import setup_jobs

from bot.handlers import admin, tools, game, public, threats

logger = logging.getLogger(__name__)

def register_all_routers(dp: Dispatcher):
    """Централизованно и явно регистрирует все роутеры приложения в правильном порядке."""
    dp.include_router(admin.admin_router)
    dp.include_router(admin.verification_admin_router)
    dp.include_router(admin.stats_router)
    dp.include_router(admin.moderation_router)
    dp.include_router(admin.game_admin_router)
    dp.include_router(tools.calculator_router)
    dp.include_router(game.mining_game_router)
    dp.include_router(public.price_router)
    dp.include_router(public.asic_router)
    dp.include_router(public.news_router)
    dp.include_router(public.quiz_router)
    dp.include_router(public.market_info_router)
    dp.include_router(public.crypto_center_router)
    dp.include_router(public.verification_public_router)
    dp.include_router(public.achievements_router)
    dp.include_router(public.market_router)
    dp.include_router(public.game_router)
    dp.include_router(public.common_router)
    dp.include_router(public.menu_router) # Важно, чтобы обработчик возврата в меню был
    dp.include_router(threats.threat_router)
    logger.info("Все роутеры успешно зарегистрированы.")

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="help", description="ℹ️ Помощь по боту"),
        BotCommand(command="check", description="✅ Проверить статус пользователя"),
        BotCommand(command="admin", description="🔒 Панель администратора"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота успешно установлены.")

async def on_startup(bot: Bot, deps: Deps):
    logger.info("Запуск процедур on_startup...")
    await set_bot_commands(bot)
    setup_jobs(deps.scheduler, deps)
    deps.scheduler.start()
    if deps.admin_service:
        await deps.admin_service.notify_admins("✅ Бот успешно запущен и готов к работе!")
    logger.info("Процедуры on_startup завершены.")

async def on_shutdown(deps: Deps):
    logger.info("Запуск процедур on_shutdown...")
    if deps.admin_service:
        await deps.admin_service.notify_admins("❗️ Бот останавливается!")
    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=True)
    if deps.redis_pool:
        await deps.redis_pool.close()
    if deps.http_session:
        await deps.http_session.close()
    logger.info("Процедуры on_shutdown завершены.")

async def main():
    setup_logging(level=settings.log_level, format="json")
    
    async with ClientSession() as http_session:
        bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML"))
        
        try:
            deps = await Deps.build(settings=settings, http_session=http_session, bot=bot)
        except Exception as e:
            logger.critical(f"Не удалось собрать зависимости: {e}", exc_info=True)
            return

        storage = RedisStorage(redis=deps.redis_pool)
        dp = Dispatcher(storage=storage, deps=deps)

        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        
        register_all_routers(dp)
        
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        await bot.delete_webhook(drop_pending_updates=True)

        # Graceful shutdown setup
        loop = asyncio.get_running_loop()
        stop_signals = (signal.SIGINT, signal.SIGTERM)
        for sig in stop_signals:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(graceful_shutdown(s, dp)))
        
        logger.info("Запуск бота...")
        await dp.start_polling(bot)

async def graceful_shutdown(s: signal.Signals, dp: Dispatcher):
    logger.warning(f"Получен сигнал {s.name}, начинаю graceful shutdown...")
    await dp.stop_polling()
    # on_shutdown будет вызван автоматически через dp.shutdown.register
    logger.warning("Graceful shutdown завершен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")