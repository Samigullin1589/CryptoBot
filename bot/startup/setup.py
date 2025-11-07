# bot/startup/setup.py
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from loguru import logger

from bot.containers import Container


async def setup_dependencies(container: Container) -> None:
    logger.info("🔧 Initializing dependencies...")
    
    try:
        container.http_client()
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
    logger.info("🤖 Setting up bot and dispatcher...")
    
    try:
        bot = container.bot()
        redis = await container.redis_client()
        storage = RedisStorage(redis=redis)
        dispatcher = Dispatcher(storage=storage)
        
        logger.info("✅ Bot and dispatcher configured")
        return bot, dispatcher
    except Exception as e:
        logger.error(f"❌ Failed to setup bot: {e}")
        raise