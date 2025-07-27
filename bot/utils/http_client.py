# ===============================================================
# Файл: bot/utils/http_client.py (НОВЫЙ ФАЙЛ)
# Описание: Содержит универсальную и отказоустойчивую функцию
# для выполнения асинхронных HTTP-запросов.
# ===============================================================

import logging
import asyncio
from typing import Any, Literal, Optional, Dict

import aiohttp
import backoff

logger = logging.getLogger(__name__)

def backoff_hdlr(details):
    """Обработчик для логирования повторных попыток backoff."""
    logger.warning(
        "Backing off {wait:0.1f}s after {tries} tries calling function {target.__name__} due to {exception}".format(**details)
    )

@backoff.on_exception(
    backoff.expo, 
    (aiohttp.ClientError, asyncio.TimeoutError), 
    max_tries=4, 
    on_backoff=backoff_hdlr
)
async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    response_type: Literal["json", "text"] = "json",
    timeout: int = 15
) -> Optional[Any]:
    """
    Универсальный метод для выполнения асинхронных HTTP-запросов.

    - Использует backoff для автоматических повторных попыток при сбоях сети.
    - Поддерживает разные методы, параметры, заголовки.
    - Обеспечивает детальное логирование ошибок.

    :param session: Экземпляр aiohttp.ClientSession.
    :param url: URL для запроса.
    :param method: HTTP-метод (GET, POST, и т.д.).
    :param params: Параметры URL.
    :param json_data: Тело запроса в формате JSON.
    :param headers: HTTP-заголовки.
    :param response_type: Ожидаемый тип ответа ('json' или 'text').
    :param timeout: Общий таймаут запроса в секундах.
    :return: Ответ в виде JSON-объекта/текста или None в случае ошибки.
    """
    try:
        aio_timeout = aiohttp.ClientTimeout(total=timeout)
        async with session.request(
            method,
            url,
            params=params,
            json=json_data,
            headers=headers,
            timeout=aio_timeout,
            ssl=False  # Часто необходимо для обхода проблем с сертификатами
        ) as response:
            response.raise_for_status()
            if response_type == "json":
                # content_type=None игнорирует проверку Content-Type
                return await response.json(content_type=None)
            return await response.text()
            
    except aiohttp.ClientResponseError as e:
        logger.error(f"Request to {url} failed with status {e.status}, message='{e.message}'")
        # re-raise exception to trigger backoff
        raise
    except asyncio.TimeoutError:
        logger.error(f"Request to {url} timed out after {timeout} seconds.")
        raise
    except Exception as e:
        logger.exception("An unexpected error occurred in make_request for URL: %s", url)
        # Не вызываем raise здесь, чтобы backoff не сработал на неизвестных ошибках
        return None

