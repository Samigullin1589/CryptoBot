# =============================================================================
# Файл: bot/main.py
# Версия: 2.3.0 - PRODUCTION READY (29.10.2025) - Distinguished Engineer
# Описание:
#   ✅ ИСПРАВЛЕНО: Добавлена защита от множественных экземпляров через Redis lock
#   ✅ ИСПРАВЛЕНО: Улучшенное удаление webhook перед polling
#   ✅ ИСПРАВЛЕНО: Graceful shutdown с proper cleanup
#   ✅ ВСЁ РАБОТАЕТ БЕЗ КОНФЛИКТОВ!
# =============================================================================

import asyncio
import logging
import signal
import sys
import time
from typing import Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.logging_setup import setup_logging
from bot.containers import Container

# Глобальные переменные для управления жизненным циклом
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
container: Optional[Container] = None
app: Optional[web.Application] = None
runner: Optional[web.AppRunner] = None
shutdown_event: Optional[asyncio.Event] = None
instance_lock_key = "bot:instance:lock"
instance_id: Optional[str] = None


# =============================================================================
# INSTANCE LOCK (ЗАЩИТА ОТ МНОЖЕСТВЕННЫХ ЭКЗЕМПЛЯРОВ)
# =============================================================================

async def acquire_instance_lock(redis: Redis) -> bool:
    """
    Пытается захватить блокировку экземпляра в Redis.
    
    Args:
        redis: Redis клиент
        
    Returns:
        True если блокировка захвачена, False если другой экземпляр уже работает
    """
    global instance_id
    
    # Генерируем уникальный ID экземпляра
    import uuid
    instance_id = f"{uuid.uuid4()}-{int(time.time())}"
    
    # Пытаемся установить блокировку с TTL 300 секунд (5 минут)
    # NX = только если ключ не существует
    lock_acquired = await redis.set(
        instance_lock_key,
        instance_id,
        nx=True,  # Только если не существует
        ex=300    # TTL 5 минут
    )
    
    if lock_acquired:
        logger.info(f"✅ Instance lock acquired: {instance_id}")
        return True
    else:
        # Проверяем кто держит блокировку
        existing_id = await redis.get(instance_lock_key)
        if existing_id:
            existing_id = existing_id.decode('utf-8') if isinstance(existing_id, bytes) else existing_id
            logger.error(f"❌ Another bot instance is already running: {existing_id}")
        return False


async def refresh_instance_lock(redis: Redis) -> None:
    """
    Периодически обновляет TTL блокировки экземпляра.
    Должна работать в фоновой задаче.
    
    Args:
        redis: Redis клиент
    """
    global instance_id
    
    while True:
        try:
            await asyncio.sleep(60)  # Обновляем каждую минуту
            
            # Проверяем, что блокировка всё ещё принадлежит нам
            current_holder = await redis.get(instance_lock_key)
            if current_holder:
                current_holder = current_holder.decode('utf-8') if isinstance(current_holder, bytes) else current_holder
                
                if current_holder == instance_id:
                    # Продлеваем TTL
                    await redis.expire(instance_lock_key, 300)
                    logger.debug(f"🔄 Instance lock refreshed: {instance_id}")
                else:
                    logger.warning(f"⚠️ Instance lock was taken by another instance: {current_holder}")
                    break
            else:
                # Блокировка пропала, пытаемся её восстановить
                logger.warning("⚠️ Instance lock disappeared, attempting to reacquire...")
                await redis.set(instance_lock_key, instance_id, ex=300)
                
        except asyncio.CancelledError:
            logger.info("🛑 Instance lock refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error refreshing instance lock: {e}")
            await asyncio.sleep(5)


async def release_instance_lock(redis: Redis) -> None:
    """
    Освобождает блокировку экземпляра.
    
    Args:
        redis: Redis клиент
    """
    global instance_id
    
    try:
        # Используем Lua скрипт для атомарного удаления только своей блокировки
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = await redis.eval(lua_script, 1, instance_lock_key, instance_id)
        
        if result:
            logger.info(f"✅ Instance lock released: {instance_id}")
        else:
            logger.warning(f"⚠️ Instance lock was not ours or already released")
            
    except Exception as e:
        logger.error(f"❌ Error releasing instance lock: {e}")


# =============================================================================
# INITIALIZATION
# =============================================================================

async def setup_dependencies() -> None:
    """Инициализация всех зависимостей (Redis, БД и т.д.)."""
    logger.info("🔧 Initializing dependencies...")
    
    try:
        # Проверяем Redis
        redis = container.redis_client()
        await redis.ping()
        logger.info("✅ Redis connected successfully")
        
        # Пытаемся захватить блокировку экземпляра (только для polling режима)
        if not settings.IS_WEB_PROCESS:
            lock_acquired = await acquire_instance_lock(redis)
            if not lock_acquired:
                logger.critical("❌ CRITICAL: Another bot instance is already running!")
                logger.critical("❌ This instance will shut down to prevent conflicts.")
                raise RuntimeError("Multiple bot instances detected - shutting down to prevent TelegramConflictError")
            
            # Запускаем фоновую задачу для обновления блокировки
            asyncio.create_task(refresh_instance_lock(redis))
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {e}")
        raise


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """
    Создание и настройка Bot и Dispatcher.
    
    Returns:
        Кортеж (Bot, Dispatcher)
    """
    logger.info("🤖 Setting up bot and dispatcher...")
    
    # Получаем бота из контейнера
    bot_instance = container.bot()
    
    # Создаём диспетчер
    dispatcher = Dispatcher()
    
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
        
        # Регистрируем роутеры
        dp.include_router(public_router)
        dp.include_router(admin_router)
        
        logger.info(f"✅ Public router: {len(public_router.sub_routers)} sub-routers registered")
        logger.info("✅ Admin router registered")
        logger.info("✅ Handlers registered successfully")
        
    except ImportError as e:
        logger.error(f"❌ Failed to import handlers: {e}")
        raise


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
    """Действия при запуске бота."""
    logger.info("🚀 Starting bot...")
    
    # Инициализация зависимостей (включая instance lock)
    await setup_dependencies()
    
    # КРИТИЧНО: Принудительно удаляем webhook перед запуском polling
    logger.info("🔄 Removing any existing webhook...")
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.warning(f"⚠️ Found existing webhook: {webhook_info.url}")
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook removed")
            # Даём Telegram API время на обработку
            await asyncio.sleep(2)
        else:
            logger.info("✅ No webhook found")
    except Exception as e:
        logger.error(f"❌ Error checking/removing webhook: {e}")
    
    # Настройка webhook или polling
    if settings.IS_WEB_PROCESS:
        webhook_url = await get_webhook_url()
        if not webhook_url:
            raise ValueError("Webhook URL not configured for web process")
        
        # Устанавливаем webhook
        webhook_info = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )
        
        logger.info(f"✅ Webhook set: {webhook_url}")
        logger.info(f"📊 Webhook info: {webhook_info}")
    else:
        # Polling mode - еще раз убедимся что webhook удален
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
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
                f"Username: @{bot_user.username}\n"
                f"ID: {bot_user.id}\n"
                f"Instance: {instance_id[:16]}..." if instance_id else "",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to notify admin: {e}")


async def on_shutdown() -> None:
    """Действия при остановке бота."""
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
    
    # Освобождаем instance lock
    if container is not None and not settings.IS_WEB_PROCESS:
        try:
            redis = container.redis_client()
            await release_instance_lock(redis)
        except Exception as e:
            logger.warning(f"⚠️ Error releasing instance lock: {e}")
    
    # Удаляем webhook
    if bot:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("✅ Webhook removed")
        except Exception as e:
            logger.warning(f"⚠️ Error removing webhook: {e}")
    
    # Закрываем Redis
    if container is not None:
        try:
            redis = container.redis_client()
            if redis is not None:
                await redis.close()
                logger.info("✅ Redis closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing Redis: {e}")
    
    logger.info("✅ Shutdown complete")


async def get_webhook_url() -> Optional[str]:
    """
    Получение URL для webhook.
    
    Returns:
        URL webhook или None
    """
    import os
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        render_url = render_url.rstrip('/')
        webhook_path = "/webhook/bot"
        return f"{render_url}{webhook_path}"
    
    return None


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint для Render."""
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
            "instance_id": instance_id[:16] if instance_id else None,
            "version": "2.3.0"
        },
        status=200
    )


# =============================================================================
# WEB SERVER (для webhook режима)
# =============================================================================

def create_app() -> web.Application:
    """Создание aiohttp приложения для webhook."""
    webhook_app = web.Application()
    
    # Health check endpoints
    webhook_app.router.add_get("/health", health_check)
    webhook_app.router.add_head("/health", health_check)
    webhook_app.router.add_get("/", health_check)
    
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
    """Запуск webhook сервера."""
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
    """Запуск в режиме polling."""
    logger.info("🔄 Starting polling mode...")
    
    try:
        # КРИТИЧНО: Еще раз проверяем что webhook удален
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.warning(f"⚠️ Webhook still exists: {webhook_info.url}, removing...")
            await bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
        
        logger.info("✅ Starting polling for updates...")
        
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
    """Обработчик системных сигналов."""
    logger.warning(f"⚠️ Received signal {signum}")
    
    # Устанавливаем событие остановки
    if shutdown_event:
        shutdown_event.set()


async def cleanup() -> None:
    """Очистка всех ресурсов."""
    logger.info("🧹 Cleaning up resources...")
    
    # Останавливаем диспетчер
    if dp:
        try:
            if hasattr(dp, 'stop_polling') and callable(dp.stop_polling):
                stop_result = dp.stop_polling()
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
    """Главная функция приложения."""
    global bot, dp, container, shutdown_event
    
    # Настраиваем логирование
    log_format = "json" if settings.logging.json_enabled else "text"
    setup_logging(level=settings.log_level, format=log_format)
    
    logger.info("=" * 60)
    logger.info("🤖 Mining AI Bot - Production Ready v2.3.0")
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
        container.wire(
            modules=[__name__],
            packages=["bot.handlers", "bot.middlewares"]
        )
        
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