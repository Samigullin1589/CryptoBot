# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ОТКАЗОУСТОЙЧИВАЯ)
# Описание: Точка входа с интегрированным Health Check сервером и
#           обработкой сигналов для Graceful Shutdown на Render.
# =================================================================================

import asyncio
import logging
import signal

import redis.asyncio as redis
from aiohttp import web, ClientSession
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

# --- Прямой импорт всех роутеров ---
from bot.handlers.admin import admin_router, verification_admin_router, stats_router, moderation_router, game_admin_router
from bot.handlers.tools import calculator_router
from bot.handlers.game import mining_game_router
from bot.handlers.public import menu_router, price_router, asic_handler, news_handler, quiz_handler, market_info_handler, market_handler, crypto_center_handler, verification_public_handler, achievements_handler, game_handler, common_router
from bot.handlers.threats import threat_router

logger = logging.getLogger(__name__)

def register_all_routers(dp: Dispatcher):
    """Централизованно и явно регистрирует все роутеры приложения в правильном порядке."""
    dp.include_router(admin_router)
    dp.include_router(verification_admin_router)
    dp.include_router(stats_router)
    dp.include_router(moderation_router)
    dp.include_router(game_admin_router)
    dp.include_router(calculator_router)
    dp.include_router(mining_game_router)
    dp.include_router(menu_router)
    dp.include_router(price_router)
    dp.include_router(asic_handler.router)
    dp.include_router(news_handler.router)
    dp.include_router(quiz_handler.router)
    dp.include_router(market_info_handler.router)
    dp.include_router(crypto_center_handler.router)
    dp.include_router(verification_public_handler.router)
    dp.include_router(achievements_handler.router)
    dp.include_router(market_handler.router)
    dp.include_router(game_handler.router)
    dp.include_router(common_router)
    dp.include_router(threat_router)
    logger.info("Все роутеры успешно зарегистрированы.")

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

# --- Health Check для Render ---
async def health_check(request: web.Request) -> web.Response:
    """Отвечает на HTTP-запросы для проверки работоспособности."""
    logger.debug("Health check эндпоинт получил запрос.")
    return web.json_response({"status": "ok"})

async def start_health_check_server():
    """Запускает простой aiohttp сервер для Health Check."""
    app = web.Application()
    app.router.add_get("/healthz", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render предоставляет переменную окружения PORT
    port = int(settings.PORT)
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Health check сервер запущен на порту {port}.")
    # Keep the server running
    while True:
        await asyncio.sleep(3600)

async def main():
    setup_logging(level=settings.log_level, format="json")
    
    async with ClientSession() as http_session:
        deps = await Deps.build(settings=settings, http_session=http_session, bot=Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML")))
        
        storage = RedisStorage(redis=deps.redis_pool)
        dp = Dispatcher(storage=storage)
        bot = deps.bot

        dp.workflow_data["deps"] = deps
        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        register_all_routers(dp)
        
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        await bot.delete_webhook(drop_pending_updates=True)
        
        # --- Graceful Shutdown & Health Check ---
        loop = asyncio.get_event_loop()
        
        # Создаем задачи для поллинга и health check
        polling_task = loop.create_task(dp.start_polling(bot, deps=deps))
        health_check_task = loop.create_task(start_health_check_server())

        # Обрабатываем сигнал SIGTERM от Render для чистого завершения
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(dp.stop_polling()))

        await asyncio.gather(polling_task, health_check_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)