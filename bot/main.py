# bot/main.py
import asyncio
import os
import sys

from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.startup import start_polling
from bot.startup.handlers import register_handlers
from bot.startup.middlewares import register_middlewares
from bot.startup.setup import setup_bot


async def run_bot() -> None:
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


async def run_health_server() -> None:
    from aiohttp import web
    
    port = int(os.environ.get("PORT", 10000))
    
    async def health_check(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "cryptobot"})
    
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/healthz", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    logger.info(f"🏥 Health check server started on 0.0.0.0:{port}")
    
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()


async def main_async() -> None:
    is_web_process = os.environ.get("IS_WEB_PROCESS", "false").lower() == "true"
    
    if is_web_process:
        logger.info("🌐 Starting in WEB mode (bot + health server)")
        await asyncio.gather(
            run_health_server(),
            run_bot()
        )
    else:
        logger.info("🤖 Starting in WORKER mode (bot only)")
        await run_bot()


def main() -> None:
    logger.info("=" * 60)
    logger.info("🤖 Mining AI Bot - Production Ready v3.0.0")
    logger.info("=" * 60)
    logger.info(f"📝 Log level: {settings.log_level}")
    logger.info(f"🔧 Mode: {'WEB (bot + health)' if settings.IS_WEB_PROCESS else 'WORKER (bot only)'}")
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