# bot/utils/http_client.py
import asyncio
import logging
from typing import Any, Literal, Optional

import aiohttp
import backoff
from bot.config.settings import EndpointsConfig

logger = logging.getLogger(__name__)


def backoff_hdlr(details):
    """Логирует информацию о повторных попытках запроса."""
    logger.warning(
        "Backing off {wait:0.1f}s after {tries} tries calling function {target.__name__} due to {exception}".format(
            **details
        )
    )


class HTTPClient:
    """
    Класс-обертка над aiohttp.ClientSession для централизованного
    управления HTTP-запросами, таймаутами и заголовками.
    """

    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self, config: Optional[EndpointsConfig] = None):
        self.config = config

    async def _get_session(self) -> aiohttp.ClientSession:
        """Лениво создает и возвращает сессию aiohttp."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                ssl=False,
            )
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def get_session(self) -> aiohttp.ClientSession:
        """Публичный доступ к сессии для обратной совместимости."""
        return await self._get_session()

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=4,
        giveup=lambda e: isinstance(e, aiohttp.ClientResponseError) and e.status == 429,
        on_backoff=backoff_hdlr,
    )
    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        response_type: Literal["json", "text"] = "json",
        timeout: int = 20,
    ) -> Any | None:
        """
        Выполняет GET-запрос с логикой повторных попыток.
        """
        session = await self._get_session()

        request_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        if headers:
            request_headers.update(headers)

        try:
            aio_timeout = aiohttp.ClientTimeout(total=timeout)
            async with session.get(
                url, params=params, headers=request_headers, timeout=aio_timeout, ssl=False
            ) as response:
                response.raise_for_status()
                if response_type == "json":
                    return await response.json(content_type=None)
                return await response.text()

        except aiohttp.ClientResponseError as e:
            logger.error(
                f"Request to {url} failed with status {e.status}, message='{e.message}'"
            )
            raise
        except asyncio.TimeoutError:
            logger.error(f"Request to {url} timed out after {timeout} seconds.")
            raise
        except Exception:
            logger.exception(
                "An unexpected error occurred in HTTPClient.get for URL: %s", url
            )
            return None

    async def close(self):
        """Корректно закрывает сессию при остановке приложения."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("HTTP client session closed.")


# Алиас для обратной совместимости
HttpClient = HTTPClient