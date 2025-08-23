# ===============================================================
# Файл: bot/utils/logging_setup.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Настраивает умное логирование для всего приложения.
# Поддерживает как текстовый, так и структурированный JSON-формат.
# ===============================================================

import logging
import sys
import json
from typing import Literal

# --- JSON Formatter для структурированного логирования ---

class JsonFormatter(logging.Formatter):
    """
    Кастомный форматер для вывода логов в виде одной JSON-строки.
    Это стандарт для современных production-систем.
    """
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)

# --- Главная функция настройки ---

def setup_logging(level: str = "INFO", format: Literal["text", "json"] = "text"):
    """
    Настраивает конфигурацию логирования для всего приложения.

    :param level: Уровень логирования (например, "INFO", "DEBUG").
    :param format: Формат вывода ('text' или 'json').
    """
    log_level = logging.getLevelName(level.upper())
    
    # Сбрасываем все предыдущие конфигурации
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Выбираем форматер в зависимости от настроек
    if format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

    # Настраиваем обработчик для вывода в консоль
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    # Применяем настройки к корневому логгеру
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(log_level)

    # Приглушаем слишком "болтливые" библиотеки
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info(f"Logging successfully configured with level {level.upper()} in {format} format.")