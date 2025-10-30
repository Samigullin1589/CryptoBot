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
        await container.http_client()
        logger.info("✅ HTTP client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize HTTP client: {e}")
        raise
    
    try:
        await container.redis_client()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise


async def setup_bot(container: Container) -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    global _bot_instance, _dispatcher_instance
    
    logger.info("🤖 Setting up bot and dispatcher...")
    
    try:
        bot = await container.bot()
        redis = await container.redis_client()
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
    
    registered_count = 0
    
    # Public handlers
    try:
        from bot.handlers.public import public_router
        dp.include_router(public_router)
        registered_count += 1
        logger.info("✅ public_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ public_router not found: {e}")
    
    # Game handlers
    try:
        from bot.handlers.game import game_router
        dp.include_router(game_router)
        registered_count += 1
        logger.info("✅ game_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ game_router not found: {e}")
    
    # Mining handlers
    try:
        from bot.handlers.game import mining_router
        dp.include_router(mining_router)
        registered_count += 1
        logger.info("✅ mining_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ mining_router not found: {e}")
    
    # Admin handlers
    try:
        from bot.handlers.admin import admin_router
        dp.include_router(admin_router)
        registered_count += 1
        logger.info("✅ admin_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ admin_router not found: {e}")
    
    logger.info(f"✅ Handlers registration completed. Total routers: {registered_count}")
    
    if registered_count == 0:
        logger.error("❌ No handlers were registered! Bot will not respond to any commands.")


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
        await asyncio.sleep(2)
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
    
    # Освобождаем ресурсы через контейнер
    await container.shutdown_resources()
    
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
    
    # Инициализация ресурсов и проверка instance lock
    try:
        await container.init_resources()
    except RuntimeError as e:
        logger.error(f"❌ Cannot start: {e}")
        logger.info("💡 Another instance is already running. Exiting...")
        return
    
    try:
        bot, dp = await setup_bot(container)
        register_handlers(dp, container)
        register_middlewares(dp, container)
        
        await start_polling(bot, dp, container)
    finally:
        await container.shutdown_resources()


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