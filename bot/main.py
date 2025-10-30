# bot/main.py

import asyncio
import signal
import sys
from typing import Optional
from contextlib import suppress

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.utils.logging_setup import setup_logging
from bot.middlewares.dependencies import DependenciesMiddleware

# Глобальные переменные
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
container: Optional[Container] = None
app: Optional[web.Application] = None
runner: Optional[web.AppRunner] = None
shutdown_event: Optional[asyncio.Event] = None


async def setup_dependencies() -> None:
    """Инициализация зависимостей"""
    logger.info("🔧 Инициализация зависимостей...")
    
    try:
        await container.init_resources()
        redis = await container.redis_client()
        await redis.ping()
        logger.info("✅ Redis подключен")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации зависимостей: {e}")
        raise


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    logger.info("🤖 Настройка бота и диспетчера...")
    
    bot_instance = await container.bot()
    dispatcher = Dispatcher()
    
    await register_handlers(dispatcher)
    await register_middlewares(dispatcher)
    
    logger.info("✅ Бот и диспетчер настроены")
    return bot_instance, dispatcher


async def register_handlers(dp: Dispatcher) -> None:
    """Регистрация обработчиков"""
    logger.info("📝 Регистрация обработчиков...")
    
    handlers_registered = 0
    
    # Public handlers
    try:
        from bot.handlers.public import public_router
        dp.include_router(public_router)
        handlers_registered += 1
        logger.info("✅ Public handlers зарегистрированы")
    except ImportError as e:
        logger.warning(f"⚠️ Public handlers не найдены: {e}")
    
    # Game handlers
    try:
        from bot.handlers.game import game_router
        dp.include_router(game_router)
        handlers_registered += 1
        logger.info("✅ Game handlers зарегистрированы")
    except ImportError as e:
        logger.warning(f"⚠️ Game handlers не найдены: {e}")
    
    # Mining handlers
    try:
        from bot.handlers.game import mining_router
        dp.include_router(mining_router)
        handlers_registered += 1
        logger.info("✅ Mining handlers зарегистрированы")
    except ImportError as e:
        logger.warning(f"⚠️ Mining handlers не найдены: {e}")
    
    # Admin handlers
    try:
        from bot.handlers.admin import admin_router
        dp.include_router(admin_router)
        handlers_registered += 1
        logger.info("✅ Admin handlers зарегистрированы")
    except ImportError as e:
        logger.warning(f"⚠️ Admin handlers не найдены: {e}")
    
    if handlers_registered == 0:
        raise RuntimeError("❌ Обработчики не зарегистрированы! Невозможно запустить бота.")
    
    logger.info(f"✅ Обработчики зарегистрированы: {handlers_registered} роутеров")


async def register_middlewares(dp: Dispatcher) -> None:
    """Регистрация middleware"""
    logger.info("🔌 Регистрация middleware...")
    
    try:
        dp.update.middleware(DependenciesMiddleware(container))
        logger.info("✅ Dependencies middleware зарегистрирован")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка регистрации middleware: {e}")


async def on_startup() -> None:
    """Действия при запуске"""
    logger.info("🚀 Запуск бота...")
    
    await setup_dependencies()
    
    # КРИТИЧНО: Удаляем webhook и pending updates для избежания конфликтов
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)  # Даем Telegram время обработать
    
    if settings.IS_WEB_PROCESS:
        webhook_url = await get_webhook_url()
        if not webhook_url:
            raise ValueError("Webhook URL не настроен для web process")
        
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )
        
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    else:
        logger.info("✅ Режим polling активирован")
    
    bot_user = await bot.get_me()
    logger.info(f"✅ Бот запущен: @{bot_user.username} (ID: {bot_user.id})")
    
    # Уведомление админа
    if settings.ADMIN_CHAT_ID:
        with suppress(Exception):
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                f"🤖 <b>Бот запущен</b>\n\n"
                f"Режим: {'Webhook' if settings.IS_WEB_PROCESS else 'Polling'}\n"
                f"Версия: 3.0.0",
                parse_mode=ParseMode.HTML
            )


async def on_shutdown() -> None:
    """Действия при остановке"""
    logger.info("🛑 Остановка бота...")
    
    # Уведомление админа
    if settings.ADMIN_CHAT_ID and bot:
        with suppress(Exception):
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                "🛑 <b>Бот остановлен</b>",
                parse_mode=ParseMode.HTML
            )
    
    # Удаляем webhook
    if bot:
        with suppress(Exception):
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("✅ Webhook удален")
    
    # Закрываем контейнер
    if container:
        with suppress(Exception):
            await container.shutdown_resources()
            logger.info("✅ Ресурсы контейнера освобождены")
    
    logger.info("✅ Остановка завершена")


async def get_webhook_url() -> Optional[str]:
    """Получить URL webhook"""
    import os
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        render_url = render_url.rstrip('/')
        return f"{render_url}/webhook/bot"
    return None


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint для Render"""
    bot_info = None
    if bot:
        with suppress(Exception):
            me = await bot.get_me()
            bot_info = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name
            }
    
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
    """Создать web приложение для webhook"""
    webhook_app = web.Application()
    
    # Health check endpoints
    webhook_app.router.add_get("/health", health_check)
    webhook_app.router.add_head("/health", health_check)
    webhook_app.router.add_get("/", health_check)
    
    # Webhook endpoint
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(webhook_app, path="/webhook/bot")
    
    setup_application(webhook_app, dp, bot=bot)
    
    return webhook_app


async def start_webhook() -> None:
    """Запуск webhook сервера"""
    global app, runner
    
    host = "0.0.0.0"
    port = settings.PORT
    
    logger.info(f"🌐 Запуск webhook сервера на {host}:{port}")
    
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    
    logger.info(f"✅ Webhook сервер запущен: http://{host}:{port}")
    logger.info(f"🔗 Webhook endpoint: /webhook/bot")
    logger.info(f"❤️ Health check: http://{host}:{port}/health")
    
    # Ждем сигнал остановки
    await shutdown_event.wait()


async def start_polling() -> None:
    """Запуск polling режима"""
    logger.info("🔄 Запуск режима polling...")
    
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False  # Обрабатываем сигналы сами
        )
    except asyncio.CancelledError:
        logger.info("⚠️ Polling отменен")
    except Exception as e:
        logger.error(f"❌ Ошибка polling: {e}", exc_info=True)
        raise


def handle_signal(signum: int) -> None:
    """Обработчик системных сигналов"""
    logger.warning(f"⚠️ Получен сигнал {signum}, начинаю graceful shutdown...")
    if shutdown_event:
        shutdown_event.set()


async def cleanup() -> None:
    """Очистка ресурсов"""
    logger.info("🧹 Очистка ресурсов...")
    
    # Останавливаем dispatcher
    if dp:
        with suppress(Exception):
            await dp.stop_polling()
    
    # Останавливаем web сервер
    if runner:
        with suppress(Exception):
            await runner.cleanup()
            logger.info("✅ Web сервер остановлен")
    
    # Закрываем сессию бота
    if bot and bot.session:
        with suppress(Exception):
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта")
    
    logger.info("✅ Очистка завершена")


async def main() -> None:
    """Главная точка входа"""
    global bot, dp, container, shutdown_event
    
    # Настройка логирования
    log_format = "json" if settings.logging.json_enabled else "text"
    setup_logging(level=settings.log_level, format=log_format)
    
    logger.info("=" * 60)
    logger.info("🤖 Mining AI Bot - Production Ready v3.0.0")
    logger.info("=" * 60)
    logger.info(f"📝 Log level: {settings.log_level}")
    logger.info(f"🔧 Mode: {'Webhook (Web)' if settings.IS_WEB_PROCESS else 'Polling (Worker)'}")
    logger.info(f"🌍 Port: {settings.PORT}")
    logger.info("=" * 60)
    
    shutdown_event = asyncio.Event()
    
    try:
        # Инициализация контейнера
        container = Container()
        container.wire(modules=[__name__])
        
        # Настройка бота
        bot, dp = await setup_bot()
        
        # Регистрация startup/shutdown хуков
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Регистрация обработчиков сигналов
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        
        # Запуск в зависимости от режима
        if settings.IS_WEB_PROCESS:
            await on_startup()
            await start_webhook()
            await on_shutdown()
        else:
            await start_polling()
        
    except KeyboardInterrupt:
        logger.info("⌨️ Прервано пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        await cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Необработанное исключение: {e}", exc_info=True)
        sys.exit(1)