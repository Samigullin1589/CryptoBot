# =================================================================================
# Файл: bot/services/price_service.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025)
# Описание: Сервис-кэш для цен, использующий MarketDataService как источник данных.
# ИСПРАВЛЕНИЕ: Интегрирован CoinAliasService для разрешения псевдонимов.
# =================================================================================

from __future__ import annotations
import logging
from typing import Dict, List, Optional

from redis.asyncio import Redis
from bot.config.settings import PriceServiceConfig
from bot.services.market_data_service import MarketDataService
from bot.services.coin_alias_service import CoinAliasService

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(
        self,
        redis: Redis,
        config: PriceServiceConfig,
        market_data_service: MarketDataService,
        coin_alias_service: CoinAliasService,
    ):
        self.redis = redis
        self.config = config
        self.market_data = market_data_service
        self.alias_service = coin_alias_service

    def _get_cache_key(self, coin_id: str) -> str:
        return f"cache:price:v4:{coin_id}:{self.config.default_vs_currency}"

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        if not coin_ids:
            return {}
        
        # Шаг 0: Преобразуем псевдонимы в реальные ID
        resolved_coin_ids: List[str] = []
        for coin_id in coin_ids:
            resolved_id = await self.alias_service.resolve_alias(coin_id)
            if resolved_id:
                resolved_coin_ids.append(resolved_id)
        coin_ids = list(set(resolved_coin_ids)) # Убираем дубликаты
            
        # Шаг 1: Инициализация и массовая проверка кэша
        prices: Dict[str, Optional[float]] = {cid: None for cid in coin_ids}
        cache_keys = [self._get_cache_key(cid) for cid in coin_ids]
        
        cached_values = await self.redis.mget(cache_keys)
        
        coins_to_fetch: List[str] = []
        for i, coin_id in enumerate(coin_ids):
            if cached_values[i] is not None:
                prices[coin_id] = float(cached_values[i])
            else:
                coins_to_fetch.append(coin_id)

        if not coins_to_fetch:
            logger.debug(f"Все {len(coin_ids)} цен найдены в кэше.")
            return prices

        logger.info(f"Цены для {len(coins_to_fetch)} монет не найдены в кэше. Запрос через MarketDataService.")

        # Шаг 2: Запрос недостающих цен через централизованный MarketDataService
        fetched_prices = await self.market_data.get_prices(coins_to_fetch)

        # Шаг 3: Обработка результатов и обновление кэша
        pipe = self.redis.pipeline()
        new_prices_to_cache = {}
        for coin_id, price in fetched_prices.items():
            prices[coin_id] = price
            if price is not None:
                new_prices_to_cache[self._get_cache_key(coin_id)] = price
        
        if new_prices_to_cache:
            pipe.mset(new_prices_to_cache)
            for key in new_prices_to_cache:
                pipe.expire(key, self.config.cache_ttl_seconds)
            await pipe.execute()
            logger.info(f"Кэш цен обновлен для {len(new_prices_to_cache)} монет.")

        return prices