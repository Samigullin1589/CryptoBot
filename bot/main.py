# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Точка входа с улучшенной архитектурой и роутингом.
# ИСПРАВЛЕНИЕ: Переход на прямые импорты роутеров для устранения
#              циклических зависимостей.
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
from bot.utils.dependencies import Deps
from bot.utils.logging_setup import setup_logging
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.jobs.scheduled_tasks import setup_jobs

# ИСПРАВЛЕНО: Роутеры импортируются напрямую из своих модулей
from bot.handlers.admin.admin_menu import admin_router
from bot.handlers.admin.verification_admin_handler import router as verification_admin_router
from bot.handlers.admin.stats_handler import stats_router
from bot.handlers.admin.moderation_handler import moderation_router
from bot.handlers.admin.game_admin_handler import router as game_admin_router

from bot.handlers.public.menu_handlers import router as menu_router
from bot.handlers.public.common_handler import router as common_router
from bot.handlers.public.price_handler import router as price_router
from bot.handlers.public.asic_handler import router as asic_router
from bot.handlers.public.news_handler import router as news_router
from bot.handlers.public.quiz_handler import router as quiz_router
from bot.handlers.public.market_info_handler import router as market_info_router
from bot.handlers.public.market_handler import router as market_router
from bot.handlers.public.crypto_center_handler import router as crypto_center_router
from bot.handlers.public.verification_public_handler import router as verification_public_router
from bot.handlers.public.achievements_handler import router as achievements_router
from bot.handlers.public.game_handler import router as game_router

from bot.handlers.game.mining_game_handler import game_router as mining_game_router
from bot.handlers.tools.calculator_handler import calculator_router
from bot.handlers.threats.threat_handler import threat_router

logger = logging.getLogger(__name__)

def register_all_routers(dp: Dispatcher):
    """Централизованно и явно регистрирует все роутеры приложения."""
    dp.include_router(admin_router)
    dp.include_router(verification_admin_router)
    dp.include_router(stats_router)
    dp.include_router(moderation_router)
    dp.include_router(game_admin_router)
    dp.include_router(mining_game_router)
    dp.include_router(calculator_router)
    dp.include_router(menu_router)
    dp.include_router(price_router)
    dp.include_router(asic_router)
    dp.include_router(news_router)
    dp.include_router(quiz_router)
    dp.include_router(market_info_router)
    dp.include_router(crypto_center_router)
    dp.include_router(verification_public_router)
    dp.include_router(achievements_router)
    dp.include_router(market_router)
    dp.include_router(game_router)
    dp.include_router(common_router)
    dp.include_router(threat_router)
    logger.info("Все роутеры успешно зарегистрированы в правильном порядке.")

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="help", description="ℹ️ Помощь по боту"),
        BotCommand(command="check", description="✅ Проверить статус пользователя"),
        BotCommand(command="infoverif", description="📄 Узнать о верификации"),
        BotCommand(command="admin", description="🔒 Панель администратора"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота успешно установлены.")

async def on_startup(bot: Bot, deps: Deps):
    logger.info("Запуск процедур on_startup...")
    await set_bot_commands(bot)
    await deps.coin_list_service.update_coin_list()
    setup_jobs(deps.scheduler, deps)
    deps.scheduler.start()
    if deps.admin_service:
        await deps.admin_service.notify_admins("✅ Бот успешно запущен!")
    logger.info("Процедуры on_startup завершены.")

async def on_shutdown(bot: Bot, deps: Deps):
    logger.info("Запуск процедур on_shutdown...")
    if deps.admin_service:
        await deps.admin_service.notify_admins("❗️ Бот останавливается!")
    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=False)
    if deps.redis_pool:
        await deps.redis_pool.close()
    if bot.session:
        await bot.session.close()
    logger.info("Процедуры on_shutdown завершены. Бот остановлен.")

async def main():
    setup_logging(level=settings.log_level, format="json")
    redis_pool = redis.from_url(str(settings.REDIS_URL), encoding="utf-8", decode_responses=True)
    storage = RedisStorage(redis=redis_pool)
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)
    register_all_routers(dp)
    async with ClientSession() as http_session:
        deps = await Deps.build(settings=settings, http_session=http_session, redis_pool=redis_pool, bot=bot)
        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, deps=deps)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)