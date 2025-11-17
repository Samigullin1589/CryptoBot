# bot/startup/handlers.py
from aiogram import Dispatcher
from loguru import logger

from bot.containers import Container


def register_handlers(dp: Dispatcher, container: Container) -> None:
    logger.info("📝 Registering handlers...")

    registered_count = 0

    try:
        from bot.handlers.public import public_router
        dp.include_router(public_router)
        registered_count += 1
        logger.info("✅ public_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ public_router not found: {e}")

    try:
        from bot.handlers.tools import calculator_router
        dp.include_router(calculator_router)
        registered_count += 1
        logger.info("✅ calculator_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ calculator_router not found: {e}")

    try:
        from bot.handlers.game import game_router
        dp.include_router(game_router)
        registered_count += 1
        logger.info("✅ game_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ game_router not found: {e}")

    try:
        from bot.handlers.game import mining_router
        dp.include_router(mining_router)
        registered_count += 1
        logger.info("✅ mining_router registered")
    except (ImportError, AttributeError) as e:
        logger.warning(f"⚠️ mining_router not found: {e}")

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