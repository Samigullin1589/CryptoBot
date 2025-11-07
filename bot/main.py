# bot/main.py
import asyncio
import sys

from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.startup import start_polling
from bot.startup.handlers import register_handlers
from bot.startup.middlewares import register_middlewares
from bot.startup.setup import setup_bot


async def main_async() -> None:
    container = Container()
    
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