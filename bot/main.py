# src/bot/main.py
import asyncio
import logging
import signal
import sys
from typing import Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.utils.logging_setup import setup_logging

bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
container: Optional[Container] = None
app: Optional[web.Application] = None
runner: Optional[web.AppRunner] = None
shutdown_event: Optional[asyncio.Event] = None


async def setup_dependencies() -> None:
    logger.info("🔧 Initializing dependencies...")
    
    try:
        await container.init_resources()
        redis = await container.redis_client()
        await redis.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {e}")
        raise


async def setup_bot() -> tuple[Bot, Dispatcher]:
    logger.info("🤖 Setting up bot and dispatcher...")
    
    bot_instance = await container.bot()
    dispatcher = Dispatcher()
    bot_instance.default = DefaultBotProperties(parse_mode=ParseMode.HTML)
    
    await register_handlers(dispatcher)
    await register_middlewares(dispatcher)
    
    logger.info("✅ Bot and dispatcher configured")
    return bot_instance, dispatcher


async def register_handlers(dp: Dispatcher) -> None:
    logger.info("📝 Registering handlers...")
    
    handlers_registered = 0
    
    # Public handlers
    try:
        from bot.handlers.public import public_router
        dp.include_router(public_router)
        handlers_registered += 1
        logger.info("✅ Public handlers registered")
    except ImportError as e:
        logger.warning(f"⚠️ Public handlers not found: {e}")
    
    # Game handlers
    try:
        from bot.handlers.game import game_router
        dp.include_router(game_router)
        handlers_registered += 1
        logger.info("✅ Game handlers registered")
    except ImportError as e:
        logger.warning(f"⚠️ Game handlers not found: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Game handlers import error: {e}")
    
    # Mining handlers
    try:
        from bot.handlers.game import mining_router
        dp.include_router(mining_router)
        handlers_registered += 1
        logger.info("✅ Mining handlers registered")
    except ImportError as e:
        logger.warning(f"⚠️ Mining handlers not found: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Mining handlers import error: {e}")
    
    # Admin handlers
    try:
        from bot.handlers.admin import admin_router
        dp.include_router(admin_router)
        handlers_registered += 1
        logger.info("✅ Admin handlers registered")
    except ImportError as e:
        logger.warning(f"⚠️ Admin handlers not found: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Admin handlers import error: {e}")
    
    if handlers_registered == 0:
        raise RuntimeError("❌ No handlers registered! Cannot start bot.")
    
    logger.info(f"✅ Handlers registered successfully: {handlers_registered} routers")


async def register_middlewares(dp: Dispatcher) -> None:
    logger.info("🔌 Registering middlewares...")
    
    try:
        from bot.utils.dependencies import dependencies_middleware
        dp.update.outer_middleware(dependencies_middleware)
        logger.info("✅ Dependencies middleware registered")
    except ImportError as e:
        logger.warning(f"⚠️ Middleware not found: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Middleware registration issue: {e}")


async def on_startup() -> None:
    logger.info("🚀 Starting bot...")
    
    await setup_dependencies()
    
    if settings.IS_WEB_PROCESS:
        webhook_url = await get_webhook_url()
        if not webhook_url:
            raise ValueError("Webhook URL not configured for web process")
        
        await bot.delete_webhook(drop_pending_updates=True)
        
        webhook_info = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )
        
        logger.info(f"✅ Webhook set: {webhook_url}")
        logger.info(f"📊 Webhook info: {webhook_info}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Polling mode enabled")
    
    bot_user = await bot.get_me()
    logger.info(f"✅ Bot started: @{bot_user.username} (ID: {bot_user.id})")
    
    if settings.ADMIN_CHAT_ID:
        try:
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                "🤖 <b>Bot Started</b>\n\n"
                f"Mode: {'Webhook' if settings.IS_WEB_PROCESS else 'Polling'}\n"
                f"Version: 3.0.0",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to notify admin: {e}")


async def on_shutdown() -> None:
    logger.info("🛑 Shutting down bot...")
    
    if settings.ADMIN_CHAT_ID and bot:
        try:
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                "🛑 <b>Bot Stopped</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    
    if bot:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("✅ Webhook removed")
        except Exception as e:
            logger.warning(f"⚠️ Error removing webhook: {e}")
    
    if container is not None:
        try:
            await container.shutdown_resources()
            logger.info("✅ Container resources released")
        except Exception as e:
            logger.warning(f"⚠️ Error shutting down container: {e}")
    
    logger.info("✅ Shutdown complete")


async def get_webhook_url() -> Optional[str]:
    import os
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        render_url = render_url.rstrip('/')
        webhook_path = "/webhook/bot"
        return f"{render_url}{webhook_path}"
    return None


async def health_check(request: web.Request) -> web.Response:
    bot_info = None
    if bot:
        try:
            me = await bot.get_me()
            bot_info = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name
            }
        except Exception:
            pass
    
    return web.json_response(
        {
            "status": "healthy",
            "bot": bot_info,
            "mode": "webhook" if settings.IS_WEB_PROCESS else "polling",
            "version": "3.0.0"
        },
        status=200
    )


def create_app() -> web.Application:
    webhook_app = web.Application()
    
    webhook_app.router.add_get("/health", health_check)
    webhook_app.router.add_head("/health", health_check)
    webhook_app.router.add_get("/", health_check)
    
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_handler.register(webhook_app, path="/webhook/bot")
    
    setup_application(webhook_app, dp, bot=bot)
    
    return webhook_app


async def start_webhook() -> None:
    global app, runner
    
    host = "0.0.0.0"
    port = settings.PORT
    
    logger.info(f"🌍 Starting webhook server on {host}:{port}")
    
    app = create_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    
    logger.info(f"✅ Webhook server started at http://{host}:{port}")
    logger.info(f"🔗 Webhook endpoint: /webhook/bot")
    logger.info(f"❤️ Health check: http://{host}:{port}/health")
    
    await shutdown_event.wait()


async def start_polling() -> None:
    logger.info("🔄 Starting polling mode...")
    
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False
        )
    except asyncio.CancelledError:
        logger.info("⚠️ Polling cancelled")
    except Exception as e:
        logger.error(f"❌ Polling error: {e}", exc_info=True)
        raise


def handle_signal(signum: int) -> None:
    logger.warning(f"⚠️ Received signal {signum}")
    
    if shutdown_event:
        shutdown_event.set()


async def cleanup() -> None:
    logger.info("🧹 Cleaning up resources...")
    
    if dp:
        try:
            if hasattr(dp, 'stop_polling') and callable(dp.stop_polling):
                stop_result = dp.stop_polling()
                if hasattr(stop_result, '__await__'):
                    await stop_result
        except Exception as e:
            logger.debug(f"Dispatcher stop: {e}")
    
    if runner:
        try:
            await runner.cleanup()
            logger.info("✅ Web server stopped")
        except Exception as e:
            logger.warning(f"⚠️ Web server cleanup error: {e}")
    
    if bot and bot.session:
        try:
            await bot.session.close()
            logger.info("✅ Bot session closed")
        except Exception as e:
            logger.warning(f"⚠️ Bot session close error: {e}")
    
    logger.info("✅ Cleanup complete")


async def main() -> None:
    global bot, dp, container, shutdown_event
    
    log_format = "json" if settings.logging.json_enabled else "text"
    setup_logging(level=settings.log_level, format=log_format)
    
    logger.info("=" * 60)
    logger.info("🤖 Mining AI Bot - Production Ready v3.0.0")
    logger.info("=" * 60)
    logger.info(f"📝 Log level: {settings.log_level}")
    logger.info(f"🔧 Mode: {'Webhook (Web Process)' if settings.IS_WEB_PROCESS else 'Polling (Worker)'}")
    logger.info(f"🌍 Port: {settings.PORT}")
    logger.info("=" * 60)
    
    shutdown_event = asyncio.Event()
    
    try:
        container = Container()
        container.wire(modules=[__name__])
        
        bot, dp = await setup_bot()
        
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        
        if settings.IS_WEB_PROCESS:
            await on_startup()
            await start_webhook()
            await on_shutdown()
        else:
            await start_polling()
            
    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        raise
    finally:
        await cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}", exc_info=True)
        sys.exit(1)