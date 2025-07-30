# ===============================================================
# Файл: bot/services/market_data_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Отказоустойчивый сервис для получения общих рыночных данных,
# с надежным кэшированием и чистой архитектурой.
# ===============================================================
import asyncio
import json
import logging
from typing import Optional, Any
from datetime import datetime

import aiohttp
import backoff
import redis.asyncio as redis

from bot.config.settings import MarketDataServiceConfig, EndpointsConfig
from bot.utils.keys import KeyFactory
from bot.utils.models import FearAndGreedIndex, HalvingInfo, NetworkStatus

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, TimeoutError)

class MarketDataService:
    """Сервис для получения данных о рынке и сети Bitcoin из внешних API."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        http_session: aiohttp.ClientSession,
        config: MarketDataServiceConfig,
        endpoints: EndpointsConfig
    ):
        self.redis = redis_client
        self.session = http_session
        self.config = config
        self.endpoints = endpoints
        self.keys = KeyFactory

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3)
    async def _fetch(self, url: str) -> Optional[Any]:
        """Выполняет отказоустойчивый HTTP-запрос."""
        async with self.session.get(url, timeout=10) as response:
            response.raise_for_status()
            return await response.json()

    async def get_fear_and_greed_index(self) -> Optional[FearAndGreedIndex]:
        """Получает Индекс Страха и Жадности."""
        cache_key = self.keys.fng_index_cache()
        cached = await self.redis.get(cache_key)
        if cached:
            return FearAndGreedIndex.model_validate_json(cached)

        try:
            data = await self._fetch(self.endpoints.fear_and_greed_api_url)
            if data and "data" in data and len(data["data"]) > 0:
                index_data = data["data"][0]
                model = FearAndGreedIndex.model_validate(index_data)
                await self.redis.set(cache_key, model.model_dump_json(), ex=self.config.fng_cache_ttl_seconds)
                logger.info(f"Fetched Fear & Greed Index: {model.value} ({model.value_classification})")
                return model
        except Exception as e:
            logger.error(f"Failed to fetch Fear & Greed Index: {e}", exc_info=True)
        
        return None

    async def get_halving_info(self) -> Optional[HalvingInfo]:
        """Получает информацию о следующем халвинге Bitcoin."""
        cache_key = self.keys.halving_info_cache()
        cached = await self.redis.get(cache_key)
        if cached:
            return HalvingInfo.model_validate_json(cached)
            
        try:
            data = await self._fetch(self.endpoints.btc_halving_url)
            if data and isinstance(data.get("data"), dict):
                halving_data = data["data"]
                next_reward = halving_data['next_halving_reward']
                
                model = HalvingInfo(
                    remaining_blocks=halving_data['blocks_to_halving'],
                    estimated_date=datetime.strptime(halving_data['next_retarget_time_estimate'], '%Y-%m-%d %H:%M:%S'),
                    current_reward=float(next_reward) * 2,
                    next_reward=float(next_reward)
                )
                await self.redis.set(cache_key, model.model_dump_json(), ex=self.config.halving_cache_ttl_seconds)
                logger.info("Fetched Halving info from Blockchair.")
                return model
        except Exception as e:
            logger.error(f"Failed to fetch or parse halving info: {e}", exc_info=True)
            
        return None

    async def get_btc_network_status(self) -> Optional[NetworkStatus]:
        """Получает агрегированную статистику сети Bitcoin."""
        cache_key = self.keys.btc_network_status_cache()
        cached = await self.redis.get(cache_key)
        if cached:
            return NetworkStatus.model_validate_json(cached)

        try:
            # Выполняем запросы параллельно
            stats_task = self._fetch(self.endpoints.btc_network_status_url)
            fees_task = self._fetch(self.endpoints.btc_fees_url)
            results = await asyncio.gather(stats_task, fees_task, return_exceptions=True)
            
            stats_data, fees_data = results
            
            # Проверяем, что оба запроса успешны
            if isinstance(stats_data, Exception) or not isinstance(stats_data.get("data"), dict):
                raise ValueError(f"Failed to get stats data: {stats_data}")
            if isinstance(fees_data, Exception):
                raise ValueError(f"Failed to get fees data: {fees_data}")

            stats = stats_data["data"]
            model = NetworkStatus(
                difficulty=stats['difficulty'],
                mempool_txs=stats['mempool_transactions'],
                fastest_fee=fees_data.get('fastestFee', 0)
            )
            await self.redis.set(cache_key, model.model_dump_json(), ex=self.config.network_status_cache_ttl_seconds)
            logger.info("Fetched BTC network status.")
            return model
        except Exception as e:
            logger.error(f"Failed to fetch BTC network status: {e}", exc_info=True)
            
        return None
