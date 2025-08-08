# =================================================================================
# Файл: bot/services/coin_list_service.py (ВЕРСИЯ "Distinguished Engineer" - ОТКАЗОУСТОЙЧИВАЯ)
# Описание: Сервис для управления списком криптовалют.
# ИСПРАВЛЕНИЕ: Добавлен механизм повторных запросов (backoff) для
# борьбы с ошибкой 429 (Too Many Requests) от API.
# =================================================================================

from __future__ import annotations
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

import aiohttp
import backoff
from redis.asyncio import Redis
from rapidfuzz import process, fuzz

from bot.config.settings import CoinListServiceConfig, EndpointsConfig
from bot.utils.models import Coin

logger = logging.getLogger(__name__)

# Определяем ошибки, при которых стоит повторять запрос
RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError)

class CoinListService:
    _COIN_LIST_CACHE_KEY = "cache:coin_list"

    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        config: CoinListServiceConfig,
        endpoints: EndpointsConfig,
    ):
        self.redis = redis
        self.http_session = http_session
        self.config = config
        self.endpoints = endpoints
        self._coin_list_url = f"{endpoints.coingecko_api_base}{endpoints.coins_list_endpoint}"

    # ИСПРАВЛЕНО: Добавлен декоратор backoff для автоматических ретраев
    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=5, logger=logger)
    async def _fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """Загружает сырой список монет с API CoinGecko с ретраями."""
        logger.info(f"Загрузка свежего списка монет с API: {self._coin_list_url}")
        async with self.http_session.get(self._coin_list_url, timeout=15) as response:
            # Вызовет исключение для кодов 4xx/5xx, которое перехватит backoff
            response.raise_for_status()
            data = await response.json()
            logger.info(f"Успешно загружено {len(data)} монет с API.")
            return data

    async def _load_fallback_data(self) -> List[Dict[str, Any]]:
        logger.warning(f"Попытка загрузить список монет из резервного файла: {self.config.fallback_file_path}")
        try:
            with open(self.config.fallback_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Успешно загружено {len(data)} монет из резервного файла.")
            return data
        except Exception as e:
            logger.error(f"Не удалось загрузить резервный файл списка монет: {e}")
            return []

    async def update_coin_list(self) -> None:
        logger.info("Запуск планового обновления списка монет.")
        try:
            coin_data = await self._fetch_from_api()
        except Exception as e:
            logger.error(f"Загрузка с API не удалась после всех попыток: {e}")
            coin_data = None

        if coin_data is None:
            coin_data = await self._load_fallback_data()

        if coin_data:
            try:
                coins = [Coin.model_validate(coin) for coin in coin_data]
                coins_to_cache = [c.model_dump(mode='json') for c in coins]
                await self.redis.set(self._COIN_LIST_CACHE_KEY, json.dumps(coins_to_cache))
                logger.info(f"Успешно обновлено и кэшировано {len(coins)} монет.")
            except Exception as e:
                logger.error(f"Не удалось валидировать или кэшировать данные монет: {e}")
        else:
            logger.error("Не удалось обновить список монет ни с API, ни из резервного файла.")

    async def get_all_coins(self) -> List[Coin]:
        cached_data = await self.redis.get(self._COIN_LIST_CACHE_KEY)
        if cached_data:
            return [Coin.model_validate(c) for c in json.loads(cached_data)]

        logger.warning("Кэш списка монет пуст. Запускаю немедленное обновление.")
        await self.update_coin_list()
        cached_data_after_update = await self.redis.get(self._COIN_LIST_CACHE_KEY)
        if cached_data_after_update:
            return [Coin.model_validate(c) for c in json.loads(cached_data_after_update)]
        return []

    async def find_coin_by_query(self, query: str) -> Optional[Coin]:
        """Ищет наиболее подходящую монету по текстовому запросу (тикер или название)."""
        query = query.lower().strip()
        all_coins = await self.get_all_coins()
        if not all_coins: return None

        for coin in all_coins:
            if coin.symbol.lower() == query:
                return coin

        choices = {coin.name: coin.id for coin in all_coins}
        best_match = process.extractOne(query, choices.keys(), scorer=fuzz.WRatio, score_cutoff=self.config.search_score_cutoff)
        
        if not best_match: return None
            
        found_name = best_match[0]
        found_coin_id = choices[found_name]
        return next((c for c in all_coins if c.id == found_coin_id), None)
