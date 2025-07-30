# ===============================================================
# Файл: bot/services/price_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Высокопроизводительный сервис для получения цен.
# Использует CoinListService для поиска и ID-based кэширование.
# ===============================================================
import logging
from typing import Optional, Any

import aiohttp
import backoff
import redis.asyncio as redis

from bot.config.settings import PriceServiceConfig, EndpointsConfig
from bot.services.coin_list_service import CoinListService
from bot.utils.keys import KeyFactory
from bot.utils.models import PriceInfo

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, TimeoutError)

class PriceService:
    """Сервис для получения цен на криптовалюты."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        http_session: aiohttp.ClientSession,
        coin_list_service: CoinListService,
        config: PriceServiceConfig,
        endpoints: EndpointsConfig
    ):
        self.redis = redis_client
        self.session = http_session
        self.coin_list_service = coin_list_service
        self.config = config
        self.endpoints = endpoints
        self.keys = KeyFactory

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3)
    async def _fetch(self, url: str, params: dict) -> Optional[Any]:
        """Выполняет отказоустойчивый HTTP-запрос."""
        async with self.session.get(url, params=params, timeout=10) as response:
            response.raise_for_status()
            return await response.json()

    async def get_crypto_price(self, query: str) -> Optional[PriceInfo]:
        """
        Получает цену криптовалюты, используя ID-based кэш и CoinGecko.
        """
        if not query:
            return None

        # 1. Находим монету с помощью нашего скоростного индекса
        coin_info = await self.coin_list_service.find_coin(query)
        if not coin_info:
            # "NOT_FOUND" кэширование больше не нужно, т.к. индекс уже сказал нам, что монеты нет.
            return None

        # 2. Проверяем кэш, используя стабильный ID монеты
        cache_key = self.keys.price_cache(coin_info.id)
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for coin_id '{coin_info.id}' from query '{query}'")
            return PriceInfo.model_validate_json(cached_data)

        # 3. Если в кэше нет, делаем запрос к API
        logger.info(f"Cache miss for coin_id '{coin_info.id}'. Fetching from API...")
        market_url = f"{self.endpoints.coingecko_api_base}/coins/markets"
        params = {"vs_currency": "usd", "ids": coin_info.id}
        
        try:
            market_data_list = await self._fetch(market_url, params=params)
            if not market_data_list or not isinstance(market_data_list, list):
                logger.error(f"CoinGecko returned invalid data for coin_id '{coin_info.id}'")
                return None
            
            market_data = market_data_list[0]
            price_info = PriceInfo.model_validate(market_data)
            
            # 4. Сохраняем результат в кэш
            await self.redis.set(
                cache_key,
                price_info.model_dump_json(),
                ex=self.config.cache_ttl_seconds
            )
            logger.info(f"Successfully fetched and cached price for '{query}' ({price_info.symbol}).")
            return price_info
            
        except Exception as e:
            logger.error(f"Failed to fetch market data for coin ID '{coin_info.id}': {e}", exc_info=True)
            return None
