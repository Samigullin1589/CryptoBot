# bot/startup/lifecycle.py
import asyncio

from aiogram import Bot
from loguru import logger

from bot.containers import Container


async def on_startup(bot: Bot, container: Container) -> None:
    logger.info("🚀 Starting bot...")
    
    from bot.startup.setup import setup_dependencies
    
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
    logger.info("🛑 Shutting down bot...")
    
    await container.shutdown_resources()
    
    logger.info("✅ Bot stopped gracefully")