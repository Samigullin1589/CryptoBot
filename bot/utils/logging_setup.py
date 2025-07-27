# ===============================================================
# Файл: bot/utils/logging_setup.py (НОВЫЙ ФАЙЛ)
# Описание: Настраивает конфигурацию логирования для всего приложения.
# Поддерживает как обычный, так и структурированный (JSON) формат.
# ===============================================================

import logging
import sys
import os

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None

def setup_logging():
    """
    Настраивает конфигурацию логирования.
    
    По умолчанию используется стандартный текстовый формат.
    Если установлена переменная окружения LOG_FORMAT=json,
    используется структурированный JSON-формат, который удобен
    для систем сбора логов (ELK, Datadog, и т.д.).
    """
    log_format = os.environ.get("LOG_FORMAT", "text")
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Получаем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Удаляем все существующие обработчики, чтобы избежать дублирования
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Создаем и настраиваем новый обработчик
    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json" and jsonlogger:
        # Форматтер для JSON-логов
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        )
        print("Logging configured in JSON format.")
    else:
        # Стандартный текстовый форматтер
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        if log_format == "json":
            print("Warning: LOG_FORMAT is 'json' but python-json-logger is not installed. Falling back to text format.")
        
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Уменьшаем "шум" от сторонних библиотек
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    # Завершаем настройку сообщением в лог
    logging.info(f"Logging successfully configured with level {log_level_str} in {log_format} format.")

