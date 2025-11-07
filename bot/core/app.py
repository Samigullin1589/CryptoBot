# bot/core/app.py
"""
Основной класс приложения.
Управляет жизненным циклом бота и health server.
"""
import asyncio
import os
import signal
from typing import Optional

from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.core.health import HealthServer
from bot.core.signals import SignalHandler
from bot.startup import start_polling
from bot.startup.handlers import register_handlers
from bot.startup.middlewares import register_middlewares
from bot.startup.setup import setup_bot


class Application:
    """Главный класс приложения, управляющий всеми компонентами."""
    
    def __init__(self):
        self.container: Optional[Container] = None
        self.health_server: Optional[HealthServer] = None
        self.signal_handler: Optional[SignalHandler] = None
        self._shutdown_event = asyncio.Event()
        
    def run(self) -> None:
        """Запуск приложения."""
        self._print_startup_banner()
        
        try:
            asyncio.run(self._run_async())
        except asyncio.CancelledError:
            logger.info("⚠️ Application cancelled")
        finally:
            logger.info("👋 Application stopped")
    
    def _print_startup_banner(self) -> None:
        """Вывод стартового баннера."""
        logger.info("=" * 70)
        logger.info("🤖 Mining AI Bot - Production Ready v3.1.0")
        logger.info("=" * 70)
        logger.info(f"📝 Log level: {settings.log_level}")
        logger.info(f"🔧 Mode: {'WEB (bot + health)' if settings.IS_WEB_PROCESS else 'WORKER (bot only)'}")
        logger.info(f"🌍 Environment: {os.environ.get('RENDER_SERVICE_NAME', 'local')}")
        logger.info("=" * 70)
    
    async def _run_async(self) -> None:
        """Асинхронный запуск всех компонентов."""
        # Инициализация signal handler
        self.signal_handler = SignalHandler(self._shutdown_event)
        self.signal_handler.setup()
        
        # Инициализация container
        self.container = Container()
        
        try:
            # Получение instance lock
            await self.container.init_resources()
        except RuntimeError as e:
            logger.error(f"❌ Cannot start: {e}")
            logger.info("💡 Another instance is already running. Exiting...")
            return
        
        try:
            # Запуск компонентов
            if settings.IS_WEB_PROCESS:
                await self._run_web_mode()
            else:
                await self._run_worker_mode()
        finally:
            await self._cleanup()
    
    async def _run_web_mode(self) -> None:
        """Запуск в режиме WEB (бот + health server)."""
        logger.info("🌐 Starting in WEB mode (bot + health server)")
        
        # Создание health server
        port = int(os.environ.get("PORT", 10000))
        self.health_server = HealthServer(port=port)
        
        # Запуск обоих компонентов
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.health_server.start())
            tg.create_task(self._run_bot())
            tg.create_task(self._wait_for_shutdown())
    
    async def _run_worker_mode(self) -> None:
        """Запуск в режиме WORKER (только бот)."""
        logger.info("🤖 Starting in WORKER mode (bot only)")
        
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._run_bot())
            tg.create_task(self._wait_for_shutdown())
    
    async def _run_bot(self) -> None:
        """Запуск и работа бота."""
        try:
            # Setup бота
            bot, dp = await setup_bot(self.container)
            register_handlers(dp, self.container)
            register_middlewares(dp, self.container)
            
            # Запуск polling
            await start_polling(bot, dp, self.container)
        except asyncio.CancelledError:
            logger.info("⚠️ Bot polling cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ Bot error: {e}", exc_info=True)
            raise
    
    async def _wait_for_shutdown(self) -> None:
        """Ожидание сигнала завершения."""
        await self._shutdown_event.wait()
        logger.info("🛑 Shutdown signal received, stopping all tasks...")
        
        # Даем время на graceful shutdown
        await asyncio.sleep(1)
    
    async def _cleanup(self) -> None:
        """Очистка всех ресурсов."""
        logger.info("🧹 Cleaning up resources...")
        
        # Остановка health server
        if self.health_server:
            try:
                await self.health_server.stop()
            except Exception as e:
                logger.error(f"Error stopping health server: {e}")
        
        # Закрытие container
        if self.container:
            try:
                await self.container.shutdown_resources()
            except Exception as e:
                logger.error(f"Error shutting down container: {e}")
        
        logger.info("✅ Cleanup completed")