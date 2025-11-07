# bot/startup/polling.py
import asyncio
import signal

from aiogram import Bot, Dispatcher
from loguru import logger

from bot.containers import Container
from bot.startup.lifecycle import on_shutdown, on_startup


_shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    logger.warning(f"⚠️ Received signal {signum}")
    _shutdown_event.set()


async def start_polling(bot: Bot, dp: Dispatcher, container: Container) -> None:
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