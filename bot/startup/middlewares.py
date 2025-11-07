# bot/startup/middlewares.py
from aiogram import Dispatcher
from loguru import logger

from bot.containers import Container
from bot.middlewares.dependencies import DependenciesMiddleware


def register_middlewares(dp: Dispatcher, container: Container) -> None:
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