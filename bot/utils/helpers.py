import logging
import sys
import re
import asyncio
from typing import Literal, Optional, Any
import aiohttp
import bleach

# Пытаемся импортировать jsonlogger, но не падаем, если его нет
try:
    from python_json_logger import jsonlogger
    JSON_LOGGER_AVAILABLE = True
except ImportError:
    JSON_LOGGER_AVAILABLE = False
    
logger = logging.getLogger(__name__)

def setup_logging():
    """
    Настраивает логирование.
    Пытается использовать JSON-формат, если библиотека доступна.
    В противном случае, использует стандартный текстовый формат.
    """
    if JSON_LOGGER_AVAILABLE:
        # Конфигурация для JSON-логгера
        log_handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s %(module)s %(funcName)s %(lineno)d'
        )
        log_handler.setFormatter(formatter)
        logging.basicConfig(
            level=logging.INFO,
            handlers=[log_handler]
        )
        logging.info("Structured JSON logging is enabled.")
    else:
        # Резервная конфигурация, если jsonlogger не найден
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(name)s - (Fallback) %(message)s",
            stream=sys.stdout,
        )
        logging.warning("python-json-logger not found. Falling back to standard text logging.")

    # Уменьшаем "шум" от некоторых библиотек
    logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    response_type: Literal['json', 'text'] = 'json',
    headers: Optional[dict] = None
) -> Optional[Any]:
    """Выполняет HTTP-запрос с обработкой ошибок и таймаутами."""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            if response_type == 'json':
                return await response.json()
            return await response.text()
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP Error: {e.status} for URL: {url}", extra={'url': url, 'message': e.message})
    except asyncio.TimeoutError:
        logger.error(f"Request Timeout for URL: {url}", extra={'url': url})
    except aiohttp.ClientError as e:
        logger.error(f"ClientError: {e.__class__.__name__} for URL: {url}")
    except Exception:
        logger.exception("Unexpected error in make_request for URL: %s", url)
    return None

def sanitize_html(text: str) -> str:
    """Очищает HTML-теги, оставляя только разрешенные для Telegram."""
    if not text:
        return ""
    return bleach.clean(text, tags=['b', 'i', 'u', 's', 'code', 'pre', 'a'], attributes={'a': ['href']}, strip=True)

def parse_profitability(s: str) -> float:
    """Извлекает числовое значение доходности из строки."""
    if not isinstance(s, str): s = str(s)
    match = re.search(r'[\d.]+', s.replace(',', '.'))
    return float(match.group(0)) if match else 0.0

def parse_power(s: str) -> Optional[int]:
    """Извлекает числовое значение мощности из строки."""
    if not isinstance(s, str): s = str(s)
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None
