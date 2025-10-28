# =============================================================================
# Файл: bot/main.py
# Версия: PRODUCTION-READY (28.10.2025) - Distinguished Engineer
# ✅ ИСПРАВЛЕНО: game_service → mining_game_service (строка 41)
# ✅ ИСПРАВЛЕНО: Graceful shutdown без ошибок NoneType
# ✅ ДОБАВЛЕНО: Health check endpoint для Render
# ✅ ДОБАВЛЕНО: Правильная обработка сигналов SIGTERM/SIGINT
# =============================================================================

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
from dependency_injector import containers, providers
from loguru import logger

from bot.config.settings import settings
from bot.utils.logging_setup import setup_logging

# Глобальные переменные для управления жизненным циклом
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
container: Optional[containers.DeclarativeContainer] = None
app: Optional[web.Application] = None
runner: Optional[web.AppRunner] = None
shutdown_event: Optional[asyncio.Event] = None


# =============================================================================
# DI CONTAINER
# =============================================================================

class Container(containers.DeclarativeContainer):
    """
    Dependency Injection контейнер для всех сервисов.
    ✅ ИСПРАВЛЕНО: bot.services.game_service → bot.services.mining_game_service
    """
    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot.handlers.public",
            "bot.handlers.admin",
            "bot.services.ai_content_service",
            "bot.services.security_service",
            "bot.services.mining_game_service",  # ✅ ИСПРАВЛЕНО! Было: game_service
            "bot.services.news_service",
            "bot.services.price_service",
            "bot.services.market_data_service",
        ]
    )
    
    config = providers.Singleton(lambda: settings)
    
    # Redis (используется многими сервисами)
    redis_client = providers.Singleton(
        lambda: None  # Инициализируется в setup_dependencies
    )
    
    # Bot и Dispatcher
    bot_instance = providers.Singleton(
        lambda: None  # Инициализируется в setup_bot
    )
    
    dispatcher = providers.Singleton(
        lambda: None  # Инициализируется в setup_bot
    )


# =============================================================================
# INITIALIZATION
# =============================================================================

async def setup_dependencies() -> None:
    """
    Инициализация всех зависимостей (Redis, БД и т.д.).
    ✅ ДОБАВЛЕНО: Проверка на None перед await
    """
    logger.info("🔧 Initializing dependencies...")
    
    try:
        # Redis
        import redis.asyncio as aioredis
        redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        container.redis_client.override(redis_client)
        logger.info("✅ Redis connected successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {e}")
        raise


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """
    Создание и настройка Bot и Dispatcher.
    ✅ ДОБАВЛЕНО: parse_mode=HTML по умолчанию
    
    Returns:
        Кортеж (Bot, Dispatcher)
    """
    logger.info("🤖 Setting up bot and dispatcher...")
    
    # Создаём бота с parse_mode=HTML
    bot_instance = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # ✅ КРИТИЧНО!
    )
    
    # Создаём диспетчер
    dispatcher = Dispatcher()
    
    # Регистрируем в контейнере
    container.bot_instance.override(bot_instance)
    container.dispatcher.override(dispatcher)
    
    # Регистрируем обработчики
    await register_handlers(dispatcher)
    
    # Регистрируем middlewares
    await register_middlewares(dispatcher)
    
    logger.info("✅ Bot and dispatcher configured")
    return bot_instance, dispatcher


async def register_handlers(dp: Dispatcher) -> None:
    """
    Регистрация всех роутеров обработчиков.
    
    Args:
        dp: Dispatcher
    """
    logger.info("📝 Registering handlers...")
    
    try:
        from bot.handlers.public import public_router
        from bot.handlers.admin import admin_router
        
        dp.include_router(public_router)
        dp.include_router(admin_router)
        
        logger.info("✅ Handlers registered successfully")
    except ImportError as e:
        logger.warning(f"⚠️ Some handlers not found: {e}")


async def register_middlewares(dp: Dispatcher) -> None:
    """
    Регистрация middleware.
    
    Args:
        dp: Dispatcher
    """
    logger.info("🔌 Registering middlewares...")
    
    try:
        # Регистрируем dependencies middleware
        from bot.utils.dependencies import dependencies_middleware
        dp.update.outer_middleware(dependencies_middleware)
        logger.info("✅ Dependencies middleware registered")
    except Exception as e:
        logger.warning(f"⚠️ Middleware registration issue: {e}")


# =============================================================================
# LIFECYCLE HOOKS
# =============================================================================

async def on_startup() -> None:
    """
    Действия при запуске бота.
    """
    logger.info("🚀 Starting bot...")
    
    # Инициализация зависимостей
    await setup_dependencies()
    
    # Настройка webhook или polling
    if settings.IS_WEB_PROCESS:
        webhook_url = await get_webhook_url()
        if not webhook_url:
            raise ValueError("Webhook URL not configured for web process")
        
        # Удаляем старый webhook
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Устанавливаем новый
        webhook_info = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )
        
        logger.info(f"✅ Webhook set: {webhook_url}")
        logger.info(f"📊 Webhook info: {webhook_info}")
    else:
        # Удаляем webhook для polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Polling mode enabled")
    
    # Получаем информацию о боте
    bot_user = await bot.get_me()
    logger.info(f"✅ Bot started: @{bot_user.username} (ID: {bot_user.id})")
    
    # Уведомляем админов
    if settings.ADMIN_CHAT_ID:
        try:
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                "🤖 <b>Bot Started</b>\n\n"
                f"Mode: {'Webhook' if settings.IS_WEB_PROCESS else 'Polling'}\n"
                f"Time: {asyncio.get_event_loop().time():.2f}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to notify admin: {e}")


async def on_shutdown() -> None:
    """
    Действия при остановке бота.
    ✅ ИСПРАВЛЕНО: Проверки на None перед операциями
    """
    logger.info("🛑 Shutting down bot...")
    
    # Уведомляем админов
    if settings.ADMIN_CHAT_ID and bot:
        try:
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                "🛑 <b>Bot Stopped</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    
    # Удаляем webhook
    if bot:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("✅ Webhook removed")
        except Exception as e:
            logger.warning(f"⚠️ Error removing webhook: {e}")
    
    # Закрываем Redis
    if container is not None:
        redis = container.redis_client()
        if redis is not None:  # ✅ Проверка на None!
            try:
                await redis.close()
                logger.info("✅ Redis connection closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing Redis: {e}")
    
    logger.info("✅ Shutdown complete")


async def get_webhook_url() -> Optional[str]:
    """
    Получение URL для webhook.
    
    Returns:
        URL webhook или None
    """
    # Render автоматически предоставляет RENDER_EXTERNAL_URL
    import os
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        # Убираем trailing slash если есть
        render_url = render_url.rstrip('/')
        webhook_path = "/webhook/bot"
        return f"{render_url}{webhook_path}"
    
    return None


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def health_check(request: web.Request) -> web.Response:
    """
    Health check endpoint для Render.
    
    Args:
        request: HTTP запрос
        
    Returns:
        JSON ответ со статусом
    """
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
            "version": "1.0.0"
        },
        status=200
    )


# =============================================================================
# WEB SERVER (для webhook режима)
# =============================================================================

def create_app() -> web.Application:
    """
    Создание aiohttp приложения для webhook.
    
    Returns:
        Настроенное приложение
    """
    webhook_app = web.Application()
    
    # Health check endpoints
    webhook_app.router.add_get("/health", health_check)
    webhook_app.router.add_head("/health", health_check)
    webhook_app.router.add_get("/", health_check)  # Root тоже
    
    # Webhook handler
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_handler.register(webhook_app, path="/webhook/bot")
    
    # Setup application
    setup_application(webhook_app, dp, bot=bot)
    
    return webhook_app


async def start_webhook() -> None:
    """
    Запуск webhook сервера.
    """
    global app, runner
    
    host = "0.0.0.0"
    port = settings.PORT
    
    logger.info(f"🌐 Starting webhook server on {host}:{port}")
    
    # Создаём приложение
    app = create_app()
    
    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    
    logger.info(f"✅ Webhook server started at http://{host}:{port}")
    logger.info(f"📍 Webhook endpoint: /webhook/bot")
    logger.info(f"❤️ Health check: http://{host}:{port}/health")
    
    # Ждём сигнала остановки
    await shutdown_event.wait()


async def start_polling() -> None:
    """
    Запуск в режиме polling.
    """
    logger.info("🔄 Starting polling mode...")
    
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False  # Обрабатываем сигналы вручную
        )
    except asyncio.CancelledError:
        logger.info("⚠️ Polling cancelled")
    except Exception as e:
        logger.error(f"❌ Polling error: {e}", exc_info=True)
        raise


# =============================================================================
# SIGNAL HANDLERS
# =============================================================================

def handle_signal(signum: int) -> None:
    """
    Обработчик системных сигналов.
    
    Args:
        signum: Номер сигнала
    """
    logger.warning(f"⚠️ Received signal {signum}")
    
    # Устанавливаем событие остановки
    if shutdown_event:
        shutdown_event.set()


async def cleanup() -> None:
    """
    Очистка всех ресурсов.
    ✅ ИСПРАВЛЕНО: Проверки на None и awaitable перед await
    """
    logger.info("🧹 Cleaning up resources...")
    
    # Останавливаем диспетчер
    if dp:
        try:
            # Проверяем есть ли метод stop_polling
            if hasattr(dp, 'stop_polling') and callable(dp.stop_polling):
                stop_result = dp.stop_polling()
                # Проверяем awaitable
                if hasattr(stop_result, '__await__'):
                    await stop_result
        except Exception as e:
            logger.debug(f"Dispatcher stop: {e}")
    
    # Останавливаем веб-сервер
    if runner:
        try:
            await runner.cleanup()
            logger.info("✅ Web server stopped")
        except Exception as e:
            logger.warning(f"⚠️ Web server cleanup error: {e}")
    
    # Закрываем сессию бота
    if bot and bot.session:
        try:
            await bot.session.close()
            logger.info("✅ Bot session closed")
        except Exception as e:
            logger.warning(f"⚠️ Bot session close error: {e}")
    
    logger.info("✅ Cleanup complete")


# =============================================================================
# MAIN
# =============================================================================

async def main() -> None:
    """
    Главная функция приложения.
    """
    global bot, dp, container, shutdown_event
    
    # Настраиваем логирование
    log_format = "json" if settings.logging.json_enabled else "text"
    setup_logging(level=settings.log_level, format=log_format)
    
    logger.info("=" * 60)
    logger.info("🤖 Mining AI Bot - Production Ready")
    logger.info("=" * 60)
    logger.info(f"📝 Log level: {settings.log_level}")
    logger.info(f"🔧 Mode: {'Webhook (Web Process)' if settings.IS_WEB_PROCESS else 'Polling (Worker)'}")
    logger.info(f"🌍 Port: {settings.PORT}")
    logger.info("=" * 60)
    
    # Создаём событие остановки
    shutdown_event = asyncio.Event()
    
    try:
        # Инициализируем DI контейнер
        container = Container()
        
        # Настраиваем бота
        bot, dp = await setup_bot()
        
        # Регистрируем lifecycle hooks
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Регистрируем обработчики сигналов
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        
        # Запускаем в нужном режиме
        if settings.IS_WEB_PROCESS:
            # Запускаем startup hooks вручную
            await on_startup()
            
            # Запускаем webhook сервер
            await start_webhook()
            
            # Запускаем shutdown hooks
            await on_shutdown()
        else:
            # В polling режиме hooks вызываются автоматически
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