# bot/main.py
"""
Точка входа приложения.
Версия: 3.0.0 Production (07.11.2025)

Архитектура запуска:
┌─────────────────────────────────────┐
│         main() entry point          │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│      async_main() coroutine         │
│  (async context manager setup)      │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│     Application().run_forever()     │
│  (bot startup and event loop)       │
└─────────────────────────────────────┘
"""
import asyncio
import sys
from typing import NoReturn

from loguru import logger

from bot.core.app import Application


async def async_main() -> None:
    """
    Асинхронная главная функция.
    
    Создает и запускает Application в правильном async контексте.
    
    Raises:
        Exception: Критические ошибки приложения
    """
    app = None
    try:
        logger.info("🚀 Starting application initialization...")
        
        app = Application()
        
        logger.info("✅ Application initialized successfully")
        logger.info("🔄 Starting main event loop...")
        
        await app.run_forever()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Received KeyboardInterrupt - shutting down gracefully")
        
    except Exception as e:
        logger.critical(
            f"❌ Critical application error: {e}",
            exc_info=True
        )
        raise
        
    finally:
        if app:
            try:
                logger.info("🛑 Stopping application...")
                await app.stop()
                logger.info("✅ Application stopped gracefully")
            except Exception as e:
                logger.error(f"⚠️ Error during shutdown: {e}", exc_info=True)


def main() -> NoReturn:
    """
    Главная точка входа приложения.
    
    Запускает асинхронное приложение через asyncio.run().
    
    Exit codes:
        0: Успешное завершение (KeyboardInterrupt)
        1: Критическая ошибка
    """
    exit_code = 0
    
    try:
        # Python 3.7+ - правильный способ запуска async приложения
        asyncio.run(async_main())
        
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
        exit_code = 0
        
    except Exception as e:
        logger.critical(
            f"💥 Fatal error in main: {e}",
            exc_info=True
        )
        exit_code = 1
        
    finally:
        logger.info(f"🏁 Exiting with code {exit_code}")
        sys.exit(exit_code)


if __name__ == "__main__":
    main()