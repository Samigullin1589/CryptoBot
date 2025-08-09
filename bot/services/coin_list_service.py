# =================================================================================
# Файл: bot/services/coin_list_service.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025 - ИСПРАВЛЕННЫЙ)
# Описание: Сервис для управления списком криптовалют с улучшенной логикой поиска.
# ИСПРАВЛЕНИЕ: Переработан метод find_coin_by_query для приоритезации точных совпадений.
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
from pydantic import ValidationError

from bot.config.config import settings
from bot.utils.models import Coin
from bot.utils.http_client import make_request

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ClientResponseError)

class CoinListService:
    _COIN_LIST_CACHE_KEY = "cache:coin_list:v3:all"
    _COIN_MAP_CACHE_KEY = "cache:coin_list:v3:map"
    _SEARCH_SYMBOL_KEY_PREFIX = "search:coin:v3:symbol"
    _SEARCH_NAME_CHOICES_KEY = "cache:coin_list:v3:name_choices"

    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        settings: Settings,
    ):
        self.redis = redis
        self.http_session = http_session
        self.settings = settings
        self.config = settings.coin_list_service
        self.endpoints = settings.endpoints

    async def _fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        url = f"{self.endpoints.coingecko_api_base}{self.endpoints.coins_list_endpoint}"
        logger.info(f"Загрузка свежего списка монет с публичного API: {url}")
        data = await make_request(self.http_session, url)
        if data:
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
        logger.info("Запуск полного обновления списка монет и поисковых индексов.")
        coin_data = await self._fetch_from_api() or await self._load_fallback_data()

        if not coin_data:
            logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Не удалось обновить список монет.")
            return

        try:
            coins = [Coin.model_validate(c) for c in coin_data]
            pipe = self.redis.pipeline()
            
            coin_map_to_cache = {c.id: c.model_dump_json() for c in coins}
            symbol_map_to_cache = {c.symbol.lower(): c.id for c in coins}
            name_choices_to_cache = {c.name: c.id for c in coins}

            pipe.hset(self._COIN_MAP_CACHE_KEY, mapping=coin_map_to_cache)
            pipe.hset(self._SEARCH_SYMBOL_KEY_PREFIX, mapping=symbol_map_to_cache)
            pipe.set(self._SEARCH_NAME_CHOICES_KEY, json.dumps(name_choices_to_cache))
            
            await pipe.execute()
            logger.info(f"Успешно обновлено и проиндексировано {len(coins)} монет.")
        except ValidationError as e:
            logger.error(f"Ошибка валидации данных монет: {e}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при кэшировании данных: {e}")

    async def find_coin_by_query(self, query: str) -> Optional[Coin]:
        query_lower = query.lower().strip()
        if not query_lower:
            return None

        # 1. Точный поиск по символу (BTC, ETH)
        found_id = await self.redis.hget(self._SEARCH_SYMBOL_KEY_PREFIX, query_lower)
        if found_id:
            coin_json = await self.redis.hget(self._COIN_MAP_CACHE_KEY, found_id)
            if coin_json:
                return Coin.model_validate_json(coin_json)

        # 2. Точный поиск по ID (bitcoin, ethereum)
        if await self.redis.hexists(self._COIN_MAP_CACHE_KEY, query_lower):
            coin_json = await self.redis.hget(self._COIN_MAP_CACHE_KEY, query_lower)
            if coin_json:
                return Coin.model_validate_json(coin_json)

        # 3. Нечеткий поиск по полному имени
        name_choices_json = await self.redis.get(self._SEARCH_NAME_CHOICES_KEY)
        if not name_choices_json:
            logger.warning("Кэш для нечеткого поиска имен пуст.")
            return None
            
        name_choices = json.loads(name_choices_json)
        best_match = process.extractOne(query_lower, name_choices.keys(), scorer=fuzz.WRatio, score_cutoff=self.config.search_score_cutoff)
        
        if best_match:
            found_name, score, _ = best_match
            found_id_by_name = name_choices[found_name]
            coin_json = await self.redis.hget(self._COIN_MAP_CACHE_KEY, found_id_by_name)
            if coin_json:
                logger.info(f"Найдена монета через нечеткий поиск: '{query}' -> '{found_name}' (счет: {score:.2f})")
                return Coin.model_validate_json(coin_json)

        logger.warning(f"Монета по запросу '{query}' не найдена.")
        return None