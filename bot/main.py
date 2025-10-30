# bot/main.py
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.middlewares.dependencies import DependenciesMiddleware


# Глобальные переменные для graceful shutdown
_shutdown_event = asyncio.Event()
_bot_instance: Bot | None = None
_dispatcher_instance: Dispatcher | None = None


def setup_dependencies(container: Container) -> None:
    """Инициализация всех зависимостей"""
    logger.info("🔧 Initializing dependencies...")
    
    container.http_client()
    container.redis_client()
    
    logger.info("✅ Redis connected successfully")


def setup_bot(container: Container) -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    global _bot_instance, _dispatcher_instance
    
    logger.info("🤖 Setting up bot and dispatcher...")
    
    bot = container.bot()
    redis = container.redis_client()
    storage = RedisStorage(redis=redis)
    dispatcher = Dispatcher(storage=storage)
    
    _bot_instance = bot
    _dispatcher_instance = dispatcher
    
    logger.info("✅ Bot and dispatcher configured")
    return bot, dispatcher


def register_handlers(dp: Dispatcher, container: Container) -> None:
    """Регистрация всех обработчиков"""
    logger.info("📝 Registering handlers...")
    
    # Public handlers
    from bot.handlers.public import command_handler, market_info_handler, price_handler
    
    dp.include_router(command_handler.router)
    dp.include_router(market_info_handler.router)
    dp.include_router(price_handler.router)
    logger.info("✅ Public handlers registered")
    
    # Game handlers (if exist)
    try:
        from bot.handlers.game import game_handler
        dp.include_router(game_handler.router)
        logger.info("✅ Game handlers registered")
    except ImportError:
        logger.warning("⚠️ Game handlers not found, skipping")
    
    # Mining handlers (if exist)
    try:
        from bot.handlers.mining import mining_handler
        dp.include_router(mining_handler.router)
        logger.info("✅ Mining handlers registered")
    except ImportError:
        logger.warning("⚠️ Mining handlers not found, skipping")
    
    # Admin handlers (if exist)
    try:
        from bot.handlers.admin import admin_handler
        dp.include_router(admin_handler.router)
        logger.info("✅ Admin handlers registered")
    except ImportError:
        logger.warning("⚠️ Admin handlers not found, skipping")
    
    logger.info("✅ Handlers registered successfully")


def register_middlewares(dp: Dispatcher, container: Container) -> None:
    """Регистрация middleware"""
    logger.info("🔌 Registering middlewares...")
    
    dp.update.middleware(DependenciesMiddleware(container))
    logger.info("✅ Dependencies middleware registered")


async def on_startup(bot: Bot, container: Container) -> None:
    """Действия при запуске бота"""
    logger.info("🚀 Starting bot...")
    
    setup_dependencies(container)
    
    # Удаляем webhook, если был установлен
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted, pending updates dropped")
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete webhook: {e}")
    
    logger.info("✅ Polling mode enabled")
    
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot started: @{bot_info.username} (ID: {bot_info.id})")


async def on_shutdown(bot: Bot, container: Container) -> None:
    """Действия при остановке бота"""
    logger.info("🛑 Shutting down bot...")
    
    try:
        # Закрываем HTTP клиент
        http_client = container.http_client()
        if http_client:
            await http_client.close()
            logger.info("✅ HTTP client closed")
    except Exception as e:
        logger.error(f"❌ Error closing HTTP client: {e}")
    
    try:
        # Закрываем Redis
        redis = container.redis_client()
        if redis:
            await redis.aclose()
            logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis: {e}")
    
    try:
        # Закрываем сессию бота
        await bot.session.close()
        logger.info("✅ Bot session closed")
    except Exception as e:
        logger.error(f"❌ Error closing bot session: {e}")
    
    logger.info("✅ Bot stopped gracefully")


def handle_signal(signum, frame):
    """Обработчик системных сигналов"""
    logger.warning(f"⚠️ Received signal {signum}")
    _shutdown_event.set()


async def start_polling(bot: Bot, dp: Dispatcher, container: Container) -> None:
    """Запуск polling с graceful shutdown"""
    logger.info("🔄 Starting polling mode...")
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        await on_startup(bot, container)
        
        # Создаем задачу polling
        polling_task = asyncio.create_task(
            dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=False,  # Обрабатываем сигналы вручную
            )
        )
        
        # Ждем сигнал остановки
        await _shutdown_event.wait()
        
        logger.info("🛑 Shutdown signal received, stopping polling...")
        
        # Отменяем polling
        polling_task.cancel()
        
        try:
            await polling_task
        except asyncio.CancelledError:
            logger.info("✅ Polling cancelled")
        
    except Exception as e:
        logger.error(f"❌ Error in polling: {e}", exc_info=True)
    finally:
        await on_shutdown(bot, container)


async def main_async() -> None:
    """Главная асинхронная функция"""
    container = Container()
    container.config.from_dict(settings.model_dump())
    
    bot, dp = setup_bot(container)
    register_handlers(dp, container)
    register_middlewares(dp, container)
    
    await start_polling(bot, dp, container)


def main() -> None:
    """Точка входа"""
    logger.info("=" * 60)
    logger.info("🤖 Mining AI Bot - Production Ready v3.0.0")
    logger.info("=" * 60)
    logger.info(f"📝 Log level: {settings.log_level}")
    logger.info(f"🔧 Mode: Polling (Worker)")
    logger.info(f"🌍 Port: {settings.port}")
    logger.info("=" * 60)
    
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("⚠️ Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("👋 Bot stopped")


if __name__ == "__main__":
    main()