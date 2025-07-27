# ===============================================================
# Файл: bot/services/coin_list_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный сервис для управления
# списком криптовалют. Использует сверхэффективное кэширование
# в Redis и интеллектуальный нечеткий поиск.
# ===============================================================

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

import aiohttp
import redis.asyncio as redis
from rapidfuzz import process, fuzz

from bot.config.settings import settings
from bot.utils.helpers import make_request
from bot.utils.models import CoinInfo

logger = logging.getLogger(__name__)

class CoinListService:
    """
    Сервис для получения, кэширования и поиска информации о криптовалютах.
    """
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session
        
        # --- Redis Keys ---
        self.CACHE_KEY = "cache:coin_list_db"
        self.LAST_UPDATE_KEY = "cache:coin_list_last_update_utc"

    async def _fetch_from_minerstat(self) -> List[CoinInfo]:
        """Получает данные с основного источника MinerStat."""
        logger.info("Fetching coin list from MinerStat...")
        minerstat_data = await make_request(self.session, f"{settings.api_endpoints.minerstat_api_base}/coins")
        if not isinstance(minerstat_data, list):
            logger.warning("Failed to fetch or invalid format from MinerStat.")
            return []
        
        coins = [
            CoinInfo(
                id=c.get('name', '').lower(),
                symbol=c.get('coin', ''),
                name=c.get('name', ''),
                algorithm=c.get('algorithm', 'Unknown')
            )
            for c in minerstat_data if c.get('coin') and c.get('name')
        ]
        logger.info(f"Successfully fetched {len(coins)} coins from MinerStat.")
        return coins

    async def _fetch_from_coingecko(self) -> List[CoinInfo]:
        """Получает данные с резервного источника CoinGecko."""
        logger.warning("MinerStat failed, using CoinGecko as a fallback.")
        gecko_data = await make_request(self.session, f"{settings.api_endpoints.coingecko_api_base}/coins/list?include_platform=false")
        if not isinstance(gecko_data, list):
            logger.error("CoinGecko fallback also failed.")
            return []
            
        coins = [
            CoinInfo(
                id=c.get('id', ''),
                symbol=c.get('symbol', '').upper(),
                name=c.get('name', ''),
                algorithm='Unknown'
            )
            for c in gecko_data if c.get('id') and c.get('symbol') and c.get('name')
        ]
        logger.info(f"Successfully fetched {len(coins)} coins from CoinGecko.")
        return coins
        
    async def update_coin_list_cache(self) -> List[CoinInfo]:
        """
        Полный цикл обновления кэша монет: получение данных из основного
        или резервного источника и сохранение в Redis.
        """
        logger.info("="*20 + " STARTING COIN LIST CACHE UPDATE " + "="*20)
        
        coin_list = await self._fetch_from_minerstat()
        if not coin_list:
            coin_list = await self._fetch_from_coingecko()

        if not coin_list:
            logger.error("Failed to fetch coin list from all sources. Cache not updated.")
            return []

        try:
            coin_list_dicts = [coin.model_dump() for coin in coin_list]
            json_data = json.dumps(coin_list_dicts, ensure_ascii=False)
            
            async with self.redis.pipeline() as pipe:
                pipe.set(self.CACHE_KEY, json_data)
                pipe.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
                await pipe.execute()
            logger.info(f"Successfully cached {len(coin_list)} coins to Redis.")
        except Exception as e:
            logger.error(f"Failed to cache coin list to Redis: {e}", exc_info=True)

        return coin_list

    async def get_all_coins_from_cache(self) -> List[CoinInfo]:
        """
        Получает и десериализует полный список монет из кэша Redis.
        Если кэш пуст, инициирует принудительное обновление.
        """
        cached_json = await self.redis.get(self.CACHE_KEY)
        if not cached_json:
            logger.warning("Coin list cache is empty. Triggering force update.")
            return await self.update_coin_list_cache()
        
        try:
            coins_dict_list = json.loads(cached_json)
            return [CoinInfo(**data) for data in coins_dict_list]
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode coin list cache from Redis: {e}. Triggering force update.")
            return await self.update_coin_list_cache()

    async def find_coin(self, query: str) -> Optional[CoinInfo]:
        """
        Интеллектуальный поиск монеты по тикеру или названию.
        Использует точные совпадения и нечеткий поиск.
        """
        query = query.strip().lower()
        if not query:
            return None

        # 1. Проверяем псевдонимы
        aliased_query = settings.ticker_aliases.get(query, query)

        all_coins = await self.get_all_coins_from_cache()
        if not all_coins:
            return None

        # 2. Ищем точное совпадение по символу (BTC, ETH)
        for coin in all_coins:
            if coin.symbol.lower() == aliased_query:
                logger.info(f"Found exact match for '{query}' by symbol: {coin.symbol}")
                return coin

        # 3. Ищем точное совпадение по ID (bitcoin, ethereum)
        for coin in all_coins:
            if coin.id.lower() == aliased_query:
                logger.info(f"Found exact match for '{query}' by ID: {coin.name}")
                return coin
        
        # 4. Если ничего не найдено, используем нечеткий поиск
        # Создаем словарь для поиска: {название: объект}
        choices_map: Dict[str, CoinInfo] = {c.name: c for c in all_coins}
        
        # extractOne возвращает кортеж (найденное_значение, оценка, ключ)
        best_match = process.extractOne(query, choices_map.keys(), scorer=fuzz.WRatio, score_cutoff=80)
        
        if best_match:
            match_name, score, _ = best_match
            logger.info(f"Found fuzzy match for '{query}': '{match_name}' with score {score:.2f}")
            return choices_map[match_name]

        logger.info(f"No coin found for query: '{query}'")
        return None

