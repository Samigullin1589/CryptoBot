# =================================================================================
# Файл: bot/services/price_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для получения цен на криптовалюты, полностью
# интегрированный в архитектуру с инъекцией зависимостей.
# ИСПРАВЛЕНИЕ: Сервис полностью переработан для соответствия DI-архитектуре.
# =================================================================================

import logging
from typing import Dict, List, Optional

import aiohttp
import backoff
from redis.asyncio import Redis

from bot.config.settings import PriceServiceConfig, EndpointsConfig
from bot.services.coin_list_service import CoinListService

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError)

class PriceService:
    """
    Отвечает за получение и кэширование цен на криптовалюты.
    """
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        coin_list_service: CoinListService,
        config: PriceServiceConfig,
        endpoints: EndpointsConfig,
    ):
        """
        Инициализирует сервис цен.

        :param redis: Асинхронный клиент Redis.
        :param http_session: Клиентская сессия aiohttp.
        :param coin_list_service: Сервис для работы со списком монет.
        :param config: Конфигурация для сервиса цен.
        :param endpoints: Конфигурация с URL-адресами API.
        """
        self.redis = redis
        self.http_session = http_session
        self.coin_list_service = coin_list_service
        self.config = config
        self.endpoints = endpoints

    def _get_cache_key(self, coin_id: str, vs_currency: str) -> str:
        """Генерирует консистентный ключ для кэша цены монеты."""
        return f"cache:price:{coin_id}:{vs_currency}"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3)
    async def get_prices(self, coin_ids: List[str], vs_currency: Optional[str] = None) -> Dict[str, Optional[float]]:
        """
        Получает цены для списка ID монет.
        Сначала проверяет кэш, затем запрашивает недостающие цены у API.
        """
        target_currency = vs_currency or self.config.default_vs_currency
        
        prices: Dict[str, Optional[float]] = {}
        coins_to_fetch: List[str] = []

        for coin_id in coin_ids:
            cache_key = self._get_cache_key(coin_id, target_currency)
            cached_price = await self.redis.get(cache_key)
            if cached_price:
                prices[coin_id] = float(cached_price)
            else:
                coins_to_fetch.append(coin_id)

        if not coins_to_fetch:
            return prices

        logger.info(f"Запрос цен с API для: {coins_to_fetch} в {target_currency}")
        
        url = f"{self.endpoints.coingecko_api_base}{self.endpoints.simple_price_endpoint}"
        params = {
            'ids': ','.join(coins_to_fetch),
            'vs_currencies': target_currency
        }
        
        try:
            async with self.http_session.get(url, params=params) as response:
                response.raise_for_status()
                api_data = await response.json()

                for coin_id in coins_to_fetch:
                    price_data = api_data.get(coin_id)
                    price = price_data.get(target_currency.lower()) if price_data else None
                    
                    if price is not None:
                        prices[coin_id] = float(price)
                        cache_key = self._get_cache_key(coin_id, target_currency)
                        await self.redis.set(cache_key, price, ex=self.config.cache_ttl_seconds)
                    else:
                        prices[coin_id] = None
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при получении цен: {e}")
            for coin_id in coins_to_fetch:
                prices[coin_id] = None
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при получении цен: {e}", exc_info=True)
            for coin_id in coins_to_fetch:
                prices[coin_id] = None

        return prices
