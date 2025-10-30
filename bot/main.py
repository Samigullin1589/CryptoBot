# bot/main.py
import asyncio
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.middlewares.dependencies import DependenciesMiddleware


_shutdown_event = asyncio.Event()
_bot_instance: Bot | None = None
_dispatcher_instance: Dispatcher | None = None


def setup_dependencies(container: Container) -> None:
    """Инициализация всех зависимостей"""
    logger.info("🔧 Initializing dependencies...")
    
    try:
        container.http_client()
        logger.info("✅ HTTP client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize HTTP client: {e}")
        raise
    
    try:
        redis = container.redis_client()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise


def setup_bot(container: Container) -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    global _bot_instance, _dispatcher_instance
    
    logger.info("🤖 Setting up bot and dispatcher...")
    
    try:
        bot = container.bot()
        redis = container.redis_client()
        storage = RedisStorage(redis=redis)
        dispatcher = Dispatcher(storage=storage)
        
        _bot_instance = bot
        _dispatcher_instance = dispatcher
        
        logger.info("✅ Bot and dispatcher configured")
        return bot, dispatcher
    except Exception as e:
        logger.error(f"❌ Failed to setup bot: {e}")
        raise


def register_handlers(dp: Dispatcher, container: Container) -> None:
    """Регистрация всех обработчиков"""
    logger.info("📝 Registering handlers...")
    
    try:
        from bot.handlers.public import command_handler, market_info_handler, price_handler
        
        dp.include_router(command_handler.router)
        dp.include_router(market_info_handler.router)
        dp.include_router(price_handler.router)
        logger.info("✅ Public handlers registered")
    except ImportError as e:
        logger.error(f"❌ Failed to import public handlers: {e}")
        raise
    
    try:
        from bot.handlers.game import game_handler
        dp.include_router(game_handler.router)
        logger.info("✅ Game handlers registered")
    except ImportError:
        logger.warning("⚠️ Game handlers not found, skipping")
    except Exception as e:
        logger.error(f"❌ Error registering game handlers: {e}")
    
    try:
        from bot.handlers.mining import mining_handler
        dp.include_router(mining_handler.router)
        logger.info("✅ Mining handlers registered")
    except ImportError:
        logger.warning("⚠️ Mining handlers not found, skipping")
    except Exception as e:
        logger.error(f"❌ Error registering mining handlers: {e}")
    
    try:
        from bot.handlers.admin import admin_handler
        dp.include_router(admin_handler.router)
        logger.info("✅ Admin handlers registered")
    except ImportError:
        logger.warning("⚠️ Admin handlers not found, skipping")
    except Exception as e:
        logger.error(f"❌ Error registering admin handlers: {e}")
    
    logger.info("✅ Handlers registration completed")


def register_middlewares(dp: Dispatcher, container: Container) -> None:
    """Регистрация middleware"""
    logger.info("🔌 Registering middlewares...")
    
    try:
        from bot.utils import dependencies as deps_module
        container.wire(modules=[deps_module])
        logger.info("✅ Container wired for dependency injection")
    except Exception as e:
        logger.warning(f"⚠️ Failed to wire container: {e}")
    
    try:
        dp.update.middleware(DependenciesMiddleware(container))
        logger.info("✅ Dependencies middleware registered")
    except Exception as e:
        logger.error(f"❌ Failed to register middleware: {e}")
        raise


async def on_startup(bot: Bot, container: Container) -> None:
    """Действия при запуске бота"""
    logger.info("🚀 Starting bot...")
    
    setup_dependencies(container)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted, pending updates dropped")
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete webhook: {e}")
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot started: @{bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        logger.error(f"❌ Failed to get bot info: {e}")
        raise
    
    logger.info("✅ Polling mode enabled")


async def on_shutdown(bot: Bot, container: Container) -> None:
    """Действия при остановке бота"""
    logger.info("🛑 Shutting down bot...")
    
    try:
        http_client = container.http_client()
        if http_client and hasattr(http_client, 'close'):
            await http_client.close()
            logger.info("✅ HTTP client closed")
    except Exception as e:
        logger.error(f"❌ Error closing HTTP client: {e}")
    
    try:
        redis = container.redis_client()
        if redis and hasattr(redis, 'aclose'):
            await redis.aclose()
            logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis: {e}")
    
    try:
        if bot.session and not bot.session.closed:
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
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        await on_startup(bot, container)
        
        polling_task = asyncio.create_task(
            dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=False,
            )
        )
        
        await _shutdown_event.wait()
        
        logger.info("🛑 Shutdown signal received, stopping polling...")
        
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