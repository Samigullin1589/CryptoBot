# ===============================================================
# Файл: bot/utils/http_client.py
# Описание: Содержит универсальную и отказоустойчивую функцию
# для выполнения асинхронных HTTP-запросов.
# ИСПРАВЛЕНИЕ: Добавлен User-Agent для обхода блокировок и
#              улучшена обработка таймаутов.
# ===============================================================

import logging
import asyncio
from typing import Any, Literal

import aiohttp
import backoff

logger = logging.getLogger(__name__)


def backoff_hdlr(details):
    logger.warning(
        "Backing off {wait:0.1f}s after {tries} tries calling function {target.__name__} due to {exception}".format(
            **details
        )
    )


@backoff.on_exception(
    backoff.expo,
    (aiohttp.ClientError, asyncio.TimeoutError),
    max_tries=4,
    on_backoff=backoff_hdlr,
)
async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    response_type: Literal["json", "text"] = "json",
    timeout: int = 15,
) -> Any | None:
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    if headers:
        request_headers.update(headers)

    try:
        aio_timeout = aiohttp.ClientTimeout(total=timeout)
        async with session.request(
            method,
            url,
            params=params,
            json=json_data,
            headers=request_headers,
            timeout=aio_timeout,
            ssl=False,  # Может быть полезно в некоторых окружениях
        ) as response:
            response.raise_for_status()
            if response_type == "json":
                # content_type=None позволяет парсить JSON с некорректным Content-Type
                return await response.json(content_type=None)
            return await response.text()

    except aiohttp.ClientResponseError as e:
        logger.error(
            f"Request to {url} failed with status {e.status}, message='{e.message}'"
        )
        # Повторная попытка будет выполнена декоратором backoff
        raise
    except TimeoutError:
        logger.error(f"Request to {url} timed out after {timeout} seconds.")
        raise
    except Exception:
        logger.exception(
            "An unexpected error occurred in make_request for URL: %s", url
        )
        return None
