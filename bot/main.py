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


async def setup_dependencies(container: Container) -> None:
    """Инициализация всех зависимостей"""
    logger.info("🔧 Initializing dependencies...")
    
    try:
        # Если это async Resource, нужно await
        http_client = container.http_client()
        if asyncio.iscoroutine(http_client) or asyncio.isfuture(http_client):
            await http_client
        logger.info("✅ HTTP client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize HTTP client: {e}")
        raise
    
    try:
        # Если это async Resource, нужно await
        redis = container.redis_client()
        if asyncio.iscoroutine(redis) or asyncio.isfuture(redis):
            await redis
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise


async def setup_bot(container: Container) -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    global _bot_instance, _dispatcher_instance
    
    logger.info("🤖 Setting up bot and dispatcher...")
    
    try:
        # Получаем bot - если это Task/coroutine, нужно await
        bot = container.bot()
        if asyncio.iscoroutine(bot) or asyncio.isfuture(bot):
            bot = await bot
        
        # Получаем redis - если это Task/coroutine, нужно await
        redis = container.redis_client()
        if asyncio.iscoroutine(redis) or asyncio.isfuture(redis):
            redis = await redis
            
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
    
    # Public handlers
    try:
        from bot.handlers import public
        
        if hasattr(public, 'router'):
            dp.include_router(public.router)
            logger.info("✅ Public handlers registered (router)")
        else:
            # Попытка импортировать отдельные модули
            try:
                from bot.handlers.public import command_handler_extended
                dp.include_router(command_handler_extended.router)
            except (ImportError, AttributeError):
                pass
                
            try:
                from bot.handlers.public import market_info_handler
                dp.include_router(market_info_handler.router)
            except (ImportError, AttributeError):
                pass
                
            try:
                from bot.handlers.public import price_handler
                dp.include_router(price_handler.router)
            except (ImportError, AttributeError):
                pass
                
            logger.info("✅ Public handlers registered (individual)")
    except Exception as e:
        logger.warning(f"⚠️ Could not register all public handlers: {e}")
    
    # Game handlers
    try:
        from bot.handlers import game
        if hasattr(game, 'router'):
            dp.include_router(game.router)
            logger.info("✅ Game handlers registered")
    except ImportError:
        logger.warning("⚠️ Game handlers not found, skipping")
    except Exception as e:
        logger.warning(f"⚠️ Error registering game handlers: {e}")
    
    # Mining handlers
    try:
        from bot.handlers import mining
        if hasattr(mining, 'router'):
            dp.include_router(mining.router)
            logger.info("✅ Mining handlers registered")
    except ImportError:
        logger.warning("⚠️ Mining handlers not found, skipping")
    except Exception as e:
        logger.warning(f"⚠️ Error registering mining handlers: {e}")
    
    # Admin handlers
    try:
        from bot.handlers import admin
        if hasattr(admin, 'router'):
            dp.include_router(admin.router)
            logger.info("✅ Admin handlers registered")
    except ImportError:
        logger.warning("⚠️ Admin handlers not found, skipping")
    except Exception as e:
        logger.warning(f"⚠️ Error registering admin handlers: {e}")
    
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
    
    await setup_dependencies(container)
    
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
        if asyncio.iscoroutine(http_client) or asyncio.isfuture(http_client):
            http_client = await http_client
        if http_client and hasattr(http_client, 'close'):
            await http_client.close()
            logger.info("✅ HTTP client closed")
    except Exception as e:
        logger.error(f"❌ Error closing HTTP client: {e}")
    
    try:
        redis = container.redis_client()
        if asyncio.iscoroutine(redis) or asyncio.isfuture(redis):
            redis = await redis
        if redis and hasattr(redis, 'aclose'):
            await redis.aclose()
            logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis: {e}")
    
    try:
        if bot and hasattr(bot, 'session') and bot.session and not bot.session.closed:
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
    
    bot, dp = await setup_bot(container)
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