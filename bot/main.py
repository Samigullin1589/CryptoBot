# bot/main.py
"""
Точка входа приложения.
Минимальная логика - только запуск application runner.
"""
import sys

from loguru import logger

from bot.core.app import Application


def main() -> None:
    """Главная точка входа."""
    try:
        app = Application()
        app.run()
    except KeyboardInterrupt:
        logger.info("⚠️ Received KeyboardInterrupt - shutting down gracefully")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"❌ Critical application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()