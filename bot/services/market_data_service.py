# ===============================================================
# Файл: bot/services/market_data_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный сервис. Использует надежное
# кэширование в Redis вместо @alru_cache. Возвращает
# Pydantic-модели вместо готовых строк для соответствия
# архитектуре "тонкий хэндлер, толстый сервис".
# ===============================================================

import json
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

import aiohttp
import redis.asyncio as redis

from bot.config.settings import settings
# --- ИСПРАВЛЕНИЕ: Импортируем утилиту из нового, правильного места ---
from bot.utils.http_client import make_request
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.models import FearAndGreedIndex, HalvingInfo, NetworkStatus

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Сервис для получения данных о рынке и сети Bitcoin из внешних API
    с надежным кэшированием в Redis.
    """
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session

    async def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Пытается получить и декодировать данные из кэша Redis."""
        cached = await self.redis.get(key)
        if cached:
            logger.debug(f"Cache hit for key: {key}")
            return json.loads(cached)
        logger.debug(f"Cache miss for key: {key}")
        return None

    async def _set_to_cache(self, key: str, data: Dict, ttl: int):
        """Сохраняет данные в кэш Redis."""
        await self.redis.set(key, json.dumps(data, default=str), ex=ttl)

    @staticmethod
    def _is_valid_price(price: any) -> bool:
        return isinstance(price, (int, float)) and price > 0

    async def get_btc_price_usd(self) -> Optional[float]:
        """Получает цену BTC/USD, используя несколько источников и кэширование."""
        cache_key = "cache:market:btc_price_usd"
        cached = await self._get_from_cache(cache_key)
        if cached and self._is_valid_price(cached.get("price")):
            return float(cached["price"])

        # Уровень 1: CryptoCompare
        data = await make_request(self.session, settings.api_endpoints.cryptocompare_api_base + "/data/price?fsym=BTC&tsyms=USD")
        if data and self._is_valid_price(data.get("USD")):
            price = float(data["USD"])
            await self._set_to_cache(cache_key, {"price": price}, ttl=600)
            logger.info(f"Fetched BTC price from CryptoCompare: ${price:,.2f}")
            return price

        # Уровень 2: CoinGecko
        data = await make_request(self.session, settings.api_endpoints.coingecko_api_base + "/simple/price?ids=bitcoin&vs_currencies=usd")
        if data and self._is_valid_price(data.get("bitcoin", {}).get("usd")):
            price = float(data["bitcoin"]["usd"])
            await self._set_to_cache(cache_key, {"price": price}, ttl=600)
            logger.info(f"Fetched BTC price from CoinGecko: ${price:,.2f}")
            return price
        
        logger.error("All BTC price sources failed.")
        return None

    async def get_fear_and_greed_index(self) -> Optional[FearAndGreedIndex]:
        """Получает Индекс Страха и Жадности."""
        cache_key = "cache:market:fng_index"
        cached = await self._get_from_cache(cache_key)
        if cached:
            return FearAndGreedIndex(**cached)

        data = await make_request(self.session, settings.api_endpoints.fear_and_greed_api_url)
        if data and "data" in data and len(data["data"]) > 0:
            index_data = data["data"][0]
            if 'value' in index_data and 'value_classification' in index_data:
                model = FearAndGreedIndex(value=int(index_data['value']), value_classification=index_data['value_classification'])
                await self._set_to_cache(cache_key, model.model_dump(), ttl=3600 * 4)
                logger.info(f"Fetched Fear & Greed Index: {model.value} ({model.value_classification})")
                return model
        
        logger.error("Failed to fetch Fear & Greed Index.")
        return None

    async def get_halving_info(self) -> Optional[HalvingInfo]:
        """Получает информацию о следующем халвинге Bitcoin."""
        cache_key = "cache:market:halving_info"
        cached = await self._get_from_cache(cache_key)
        if cached:
            # Pydantic v2 автоматически парсит ISO строки в datetime
            return HalvingInfo(**cached)

        data = await make_request(self.session, settings.api_endpoints.blockchair_api_base + "/bitcoin/stats")
        if data and isinstance(data.get("data"), dict):
            halving_data = data["data"]
            try:
                estimated_date_str = halving_data['next_halving_estimated_date']
                next_reward = halving_data['next_halving_reward']
                
                model = HalvingInfo(
                    remaining_blocks=halving_data['next_halving_blocks'],
                    estimated_date=datetime.strptime(estimated_date_str, '%Y-%m-%d %H:%M:%S'),
                    current_reward=float(next_reward) * 2,
                    next_reward=float(next_reward)
                )
                
                await self._set_to_cache(cache_key, model.model_dump(), ttl=3600)
                logger.info("Fetched Halving info from Blockchair.")
                return model
            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"Error parsing halving data from Blockchair: {e}")
        
        logger.error("Failed to fetch halving info.")
        return None

    async def get_btc_network_status(self) -> Optional[NetworkStatus]:
        """Получает агрегированную статистику сети Bitcoin."""
        cache_key = "cache:market:btc_network_status"
        cached = await self._get_from_cache(cache_key)
        if cached:
            return NetworkStatus(**cached)

        stats_task = make_request(self.session, settings.api_endpoints.blockchair_api_base + "/bitcoin/stats")
        fees_task = make_request(self.session, settings.api_endpoints.btc_fees_url)
        stats_data, fees_data = await asyncio.gather(stats_task, fees_task)

        if stats_data and isinstance(stats_data.get("data"), dict):
            stats = stats_data["data"]
            try:
                model = NetworkStatus(
                    difficulty=stats['difficulty'],
                    mempool_txs=stats['mempool_transactions'],
                    fastest_fee=fees_data.get('fastestFee', 0) if fees_data else 0
                )
                await self._set_to_cache(cache_key, model.model_dump(), ttl=60)
                logger.info("Fetched BTC network status.")
                return model
            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"Error parsing network status data: {e}")

        logger.error("Failed to fetch BTC network status.")
        return None
