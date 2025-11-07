# bot/core/app.py
"""
Основной класс приложения.
Версия: 3.0.0 Production (07.11.2025)

Управляет жизненным циклом бота и health server.

Архитектура:
┌─────────────────────────────────────┐
│         Application Class           │
├─────────────────────────────────────┤
│  - Container (DI)                   │
│  - HealthServer (HTTP)              │
│  - SignalHandler (SIGTERM/SIGINT)   │
│  - Bot & Dispatcher                 │
└─────────────────────────────────────┘
"""
import asyncio
import os
from typing import Optional

from aiogram import Bot, Dispatcher
from loguru import logger

from bot.config.settings import settings
from bot.containers import Container
from bot.containers.container import (
    init_container_resources,
    shutdown_container_resources,
)
from bot.core.health import HealthServer
from bot.core.signals import SignalHandler
from bot.startup import start_polling
from bot.startup.handlers import register_handlers
from bot.startup.middlewares import register_middlewares
from bot.startup.setup import setup_bot


class Application:
    """
    Главный класс приложения.
    
    Управляет жизненным циклом всех компонентов:
    - Dependency Injection Container
    - Telegram Bot & Dispatcher
    - Health Check Server
    - Signal Handlers
    - Graceful Shutdown
    """
    
    def __init__(self):
        """Инициализирует приложение без запуска компонентов."""
        self.container: Optional[Container] = None
        self.health_server: Optional[HealthServer] = None
        self.signal_handler: Optional[SignalHandler] = None
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        
        self._shutdown_event = asyncio.Event()
        self._is_running = False
        self._tasks: list[asyncio.Task] = []
        
        logger.debug("✅ Application instance created")
    
    async def run_forever(self) -> None:
        """
        Запускает приложение и работает до сигнала остановки.
        
        Основной метод для запуска приложения.
        Блокируется до получения сигнала завершения.
        
        Raises:
            RuntimeError: Если приложение уже запущено
            Exception: Критические ошибки инициализации
        """
        if self._is_running:
            raise RuntimeError("Application is already running")
        
        self._print_startup_banner()
        
        try:
            self._is_running = True
            
            await self._initialize()
            await self._start_components()
            await self._wait_for_shutdown()
            
        except asyncio.CancelledError:
            logger.info("⚠️ Application cancelled")
            raise
            
        except Exception as e:
            logger.critical(f"❌ Fatal error in run_forever: {e}", exc_info=True)
            raise
            
        finally:
            self._is_running = False
    
    async def stop(self) -> None:
        """
        Останавливает приложение gracefully.
        
        Вызывается из finally блока в main.py
        или может быть вызван вручную.
        """
        if not self._is_running and not self._tasks:
            logger.debug("⚠️ Application already stopped")
            return
        
        logger.info("🛑 Stopping application...")
        
        try:
            self._shutdown_event.set()
            await self._cancel_all_tasks()
            await self._cleanup()
            
            logger.info("✅ Application stopped successfully")
            
        except Exception as e:
            logger.error(f"⚠️ Error during stop: {e}", exc_info=True)
    
    def _print_startup_banner(self) -> None:
        """Выводит информационный баннер при старте."""
        logger.info("=" * 70)
        logger.info("🤖 Mining AI Bot - Production Ready v3.1.0")
        logger.info("=" * 70)
        logger.info(f"📝 Log level: {settings.log_level}")
        
        mode = "WEB (bot + health)" if settings.IS_WEB_PROCESS else "WORKER (bot only)"
        logger.info(f"🔧 Mode: {mode}")
        
        env = os.environ.get("RENDER_SERVICE_NAME", "local")
        logger.info(f"🌍 Environment: {env}")
        
        logger.info("=" * 70)
    
    async def _initialize(self) -> None:
        """
        Инициализирует все компоненты приложения.
        
        Порядок инициализации:
        1. Signal Handler
        2. DI Container
        3. Container Resources (Redis, Lock, HTTP)
        4. Bot & Dispatcher
        5. Handlers & Middlewares
        
        Raises:
            RuntimeError: Если другой instance уже запущен
            Exception: Критические ошибки инициализации
        """
        logger.info("🔧 Initializing application components...")
        
        self._init_signal_handler()
        self._init_container()
        await self._init_container_resources()
        await self._init_bot_and_dispatcher()
        self._register_handlers_and_middlewares()
        
        logger.info("✅ All components initialized successfully")
    
    def _init_signal_handler(self) -> None:
        """Инициализирует обработчик сигналов."""
        self.signal_handler = SignalHandler(self._shutdown_event)
        self.signal_handler.setup()
        logger.debug("✅ Signal handler initialized")
    
    def _init_container(self) -> None:
        """Инициализирует DI контейнер."""
        self.container = Container()
        logger.debug("✅ Container created")
    
    async def _init_container_resources(self) -> None:
        """
        Инициализирует ресурсы контейнера.
        
        Вызывает внешнюю async функцию init_container_resources().
        
        Raises:
            RuntimeError: Если другой instance уже запущен
            Exception: Критические ошибки инициализации
        """
        try:
            await init_container_resources(self.container)
            logger.debug("✅ Container resources initialized")
            
        except RuntimeError as e:
            logger.error(f"❌ Cannot acquire instance lock: {e}")
            logger.info("💡 Another instance is already running")
            raise
            
        except Exception as e:
            logger.error(f"❌ Container initialization failed: {e}", exc_info=True)
            raise
    
    async def _init_bot_and_dispatcher(self) -> None:
        """Инициализирует Bot и Dispatcher."""
        try:
            self.bot, self.dp = await setup_bot(self.container)
            logger.debug("✅ Bot and Dispatcher created")
            
        except Exception as e:
            logger.error(f"❌ Bot initialization failed: {e}", exc_info=True)
            raise
    
    def _register_handlers_and_middlewares(self) -> None:
        """Регистрирует handlers и middlewares."""
        try:
            register_handlers(self.dp, self.container)
            logger.debug("✅ Handlers registered")
            
            register_middlewares(self.dp, self.container)
            logger.debug("✅ Middlewares registered")
            
        except Exception as e:
            logger.error(f"❌ Handler registration failed: {e}", exc_info=True)
            raise
    
    async def _start_components(self) -> None:
        """
        Запускает все компоненты в фоновых задачах.
        
        Компоненты:
        - Bot Polling (всегда)
        - Health Server (только в WEB режиме)
        """
        logger.info("🚀 Starting application components...")
        
        self._start_bot_polling()
        
        if settings.IS_WEB_PROCESS:
            self._start_health_server()
        
        logger.info(f"✅ Started {len(self._tasks)} component(s)")
    
    def _start_bot_polling(self) -> None:
        """Создает задачу для bot polling."""
        bot_task = asyncio.create_task(
            self._run_bot(),
            name="bot_polling"
        )
        self._tasks.append(bot_task)
        logger.debug("✅ Bot polling task created")
    
    def _start_health_server(self) -> None:
        """Создает задачу для health server."""
        port = int(os.environ.get("PORT", 10000))
        self.health_server = HealthServer(port=port)
        
        health_task = asyncio.create_task(
            self.health_server.start(),
            name="health_server"
        )
        self._tasks.append(health_task)
        logger.debug(f"✅ Health server task created (port {port})")
    
    async def _run_bot(self) -> None:
        """
        Запускает и поддерживает работу бота.
        
        Raises:
            Exception: Критические ошибки бота
        """
        try:
            logger.info("🤖 Starting bot polling...")
            
            await start_polling(self.bot, self.dp, self.container)
            
            logger.info("✅ Bot polling completed")
            
        except asyncio.CancelledError:
            logger.info("⚠️ Bot polling cancelled")
            raise
            
        except Exception as e:
            logger.error(f"❌ Bot error: {e}", exc_info=True)
            self._shutdown_event.set()
            raise
    
    async def _wait_for_shutdown(self) -> None:
        """
        Ожидает сигнала завершения.
        
        Блокируется до:
        - SIGTERM/SIGINT
        - Критической ошибки в компонентах
        - Вызова stop()
        """
        logger.info("⏳ Application running. Waiting for shutdown signal...")
        
        await self._shutdown_event.wait()
        
        logger.info("🛑 Shutdown signal received")
    
    async def _cancel_all_tasks(self) -> None:
        """Отменяет все фоновые задачи gracefully."""
        if not self._tasks:
            return
        
        logger.info(f"⏹️ Cancelling {len(self._tasks)} task(s)...")
        
        for task in self._tasks:
            if not task.done():
                task.cancel()
                logger.debug(f"⏹️ Cancelled task: {task.get_name()}")
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=5.0
            )
            logger.debug("✅ All tasks cancelled gracefully")
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ Some tasks did not finish in time")
        
        self._tasks.clear()
    
    async def _cleanup(self) -> None:
        """
        Очищает все ресурсы приложения.
        
        Порядок очистки:
        1. Health Server
        2. Bot Session
        3. Container Resources
        """
        logger.info("🧹 Cleaning up resources...")
        
        await self._cleanup_health_server()
        await self._cleanup_bot_session()
        await self._cleanup_container()
        
        logger.info("✅ Cleanup completed")
    
    async def _cleanup_health_server(self) -> None:
        """Останавливает health server."""
        if self.health_server:
            try:
                await self.health_server.stop()
                logger.debug("✅ Health server stopped")
            except Exception as e:
                logger.error(f"⚠️ Error stopping health server: {e}")
    
    async def _cleanup_bot_session(self) -> None:
        """Закрывает сессию бота."""
        if self.bot:
            try:
                await self.bot.session.close()
                logger.debug("✅ Bot session closed")
            except Exception as e:
                logger.error(f"⚠️ Error closing bot session: {e}")
    
    async def _cleanup_container(self) -> None:
        """
        Очищает ресурсы контейнера.
        
        Вызывает внешнюю async функцию shutdown_container_resources().
        """
        if self.container:
            try:
                await shutdown_container_resources(self.container)
                logger.debug("✅ Container shutdown")
            except Exception as e:
                logger.error(f"⚠️ Error shutting down container: {e}")
    
    @property
    def is_running(self) -> bool:
        """Проверяет, запущено ли приложение."""
        return self._is_running
    
    def __repr__(self) -> str:
        """Строковое представление приложения."""
        status = "running" if self._is_running else "stopped"
        tasks = len(self._tasks)
        return f"<Application status={status} tasks={tasks}>"