# =============================================================================
# Файл: bot/utils/logging_setup.py
# Версия: PRODUCTION-READY (28.10.2025) - Distinguished Engineer
# Описание: 
#   • Умная настройка логирования через loguru
#   • Поддержка JSON-формата для structured logging
#   • Фильтрация шумных библиотек
#   • Интеграция с Python logging
# =============================================================================

import logging
import sys
from typing import Literal

from loguru import logger


# =============================================================================
# LOGURU INTERCEPTOR
# =============================================================================

class InterceptHandler(logging.Handler):
    """
    Перехватчик стандартных логов Python и перенаправление в loguru.
    Это нужно для библиотек, которые используют стандартный logging.
    """
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Перехват и отправка лога в loguru.
        
        Args:
            record: Запись лога из стандартного logging
        """
        # Получаем уровень loguru из стандартного logging
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # Находим правильный caller
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# =============================================================================
# SETUP FUNCTION
# =============================================================================

def setup_logging(
    level: str = "INFO",
    format: Literal["text", "json"] = "text"
) -> None:
    """
    Настраивает систему логирования для всего приложения.
    
    Args:
        level: Уровень логирования ("DEBUG", "INFO", "WARNING", "ERROR")
        format: Формат вывода ("text" или "json")
    """
    # Удаляем стандартные обработчики loguru
    logger.remove()
    
    # Выбираем формат
    if format == "json":
        # JSON формат для structured logging (продакшен)
        log_format = (
            '{{"timestamp":"{time:YYYY-MM-DD HH:mm:ss.SSS}","level":"{level}",'
            '"name":"{name}","function":"{function}","line":{line},'
            '"message":"{message}"}}'
        )
        colorize = False
    else:
        # Человекочитаемый формат (разработка)
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        colorize = True
    
    # Добавляем обработчик для stdout
    logger.add(
        sys.stdout,
        format=log_format,
        level=level.upper(),
        colorize=colorize,
        backtrace=True,
        diagnose=True,
    )
    
    # Перехватываем стандартный logging и направляем в loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Настраиваем уровни для шумных библиотек
    for logger_name in [
        "aiogram",
        "aiohttp",
        "asyncio",
        "apscheduler",
        "httpx",
        "httpcore",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    logger.info(
        f"✅ Logging configured: level={level.upper()}, format={format}"
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_logger(name: str):
    """
    Получение логгера для модуля.
    
    Args:
        name: Имя логгера (обычно __name__)
        
    Returns:
        Логгер loguru
    """
    return logger.bind(name=name)