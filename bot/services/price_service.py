# ===============================================================
# Файл: bot/services/price_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный сервис. Использует новый,
# "умный" CoinListService для поиска монет и надежный
# источник CoinGecko для получения рыночных данных.
# ===============================================================
import logging
from typing import Optional

import aiohttp
import redis.asyncio as redis

from bot.config.settings import settings
from bot.services.coin_list_service import CoinListService
# --- ИСПРАВЛЕНИЕ: Импортируем утилиту из нового, правильного места ---
from bot.utils.http_client import make_request
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.models import PriceInfo

logger = logging.getLogger(__name__)

class PriceService:
    """
    Сервис для получения цен на криптовалюты.
    """
    def __init__(
        self,
        coin_list_service: CoinListService,
        redis_client: redis.Redis,
        http_session: aiohttp.ClientSession
    ):
        self.coin_list_service = coin_list_service
        self.redis = redis_client
        self.session = http_session
        self.config = settings.price_service

    async def get_crypto_price(self, query: str) -> Optional[PriceInfo]:
        """
        Получает цену криптовалюты, используя кэш в Redis и CoinGecko.
        """
        query_norm = settings.app.ticker_aliases.get(query.strip().lower(), query.strip().lower())
        if not query_norm:
            return None

        cache_key = f"price_cache:{query_norm}"
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            cached_str = cached_data.decode('utf-8')
            if cached_str == "NOT_FOUND":
                logger.debug(f"Cache hit 'NOT_FOUND' for query: '{query}'")
                return None
            logger.debug(f"Cache hit for query: '{query}'")
            return PriceInfo.model_validate_json(cached_str)

        logger.info(f"Cache miss for query: '{query}'. Searching for coin...")
        coin_info = await self.coin_list_service.find_coin(query_norm)
        if not coin_info:
            logger.warning(f"Coin not found for query: '{query}'. Caching as 'NOT_FOUND'.")
            await self.redis.set(cache_key, "NOT_FOUND", ex=self.config.not_found_cache_ttl)
            return None

        market_url = f"{settings.api_endpoints.coingecko_api_base}/coins/markets"
        params = {"vs_currency": "usd", "ids": coin_info.name} # Используем name, так как это ID в CoinGecko
        
        market_data_list = await make_request(self.session, market_url, params=params)

        if market_data_list and isinstance(market_data_list, list):
            market_data = market_data_list[0]
            # Дополняем рыночные данные алгоритмом из нашего справочника
            market_data['algorithm'] = coin_info.algorithm
            
            price_info = PriceInfo.model_validate(market_data)
            
            await self.redis.set(cache_key, price_info.model_dump_json(), ex=self.config.cache_ttl)
            logger.info(f"Successfully fetched and cached price for '{query}' ({price_info.symbol}).")
            return price_info
        
        logger.error(f"Failed to fetch market data for coin ID '{coin_info.name}' from CoinGecko.")
        # Не кэшируем ошибку API, чтобы можно было попробовать снова
        return None
