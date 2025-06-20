import logging
import sys
import re
import asyncio
from typing import Literal, Optional, Any
import aiohttp
import bleach
from python_json_logger import jsonlogger

logger = logging.getLogger(__name__)

def setup_logging():
    """Настраивает структурированное JSON-логирование."""
    log_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(module)s %(funcName)s %(lineno)d'
    )
    log_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[log_handler]
    )

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
        logger.error(f"HTTP Error: {e.status}", extra={'url': url, 'message': e.message})
    except asyncio.TimeoutError:
        logger.error("Request Timeout", extra={'url': url})
    except aiohttp.ClientError as e:
        logger.error(f"ClientError: {e.__class__.__name__}", extra={'url': url})
    except Exception as e:
        logger.exception("Unexpected error in make_request")
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