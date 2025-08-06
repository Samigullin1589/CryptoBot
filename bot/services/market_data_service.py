# =================================================================================
# Файл: bot/services/market_data_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для получения рыночных данных, полностью
# интегрированный в архитектуру с инъекцией зависимостей.
# ИСПРАВЛЕНИЕ: Добавлен недостающий импорт 'asyncio'.
# =================================================================================

import logging
import asyncio # <--- ИСПРАВЛЕНО: Добавлен недостающий импорт
from typing import List, Optional, Dict, Any

import aiohttp
import backoff
from redis.asyncio import Redis

from bot.config.settings import MarketDataServiceConfig, EndpointsConfig

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError)

class MarketDataService:
    """
    Отвечает за получение общих рыночных данных, таких как топ монет.
    """
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        config: MarketDataServiceConfig,
        endpoints: EndpointsConfig,
    ):
        """
        Инициализирует сервис рыночных данных.

        :param redis: Асинхронный клиент Redis.
        :param http_session: Клиентская сессия aiohttp.
        :param config: Конфигурация для сервиса рыночных данных.
        :param endpoints: Конфигурация с URL-адресами API.
        """
        self.redis = redis
        self.http_session = http_session
        self.config = config
        self.endpoints = endpoints

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3)
    async def get_top_coins_by_market_cap(self) -> Optional[List[Dict[str, Any]]]:
        """Загружает топ-N монет по рыночной капитализации с CoinGecko."""
        
        url = f"{self.endpoints.coingecko_api_base}{self.endpoints.coins_markets_endpoint}"
        params = {
            'vs_currency': self.config.default_vs_currency,
            'order': 'market_cap_desc',
            'per_page': self.config.top_n_coins,
            'page': 1,
            'sparkline': 'false',
            'price_change_percentage': '1h,24h,7d'
        }
        
        logger.info(f"Запрос топ-{self.config.top_n_coins} монет с API: {url}")
        try:
            async with self.http_session.get(url, params=params, timeout=20) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Успешно загружено {len(data)} монет с API.")
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при загрузке рыночных данных: {e}")
            return None
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при загрузке рыночных данных: {e}", exc_info=True)
            return None
