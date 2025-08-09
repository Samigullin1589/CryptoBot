# =================================================================================
# Файл: bot/services/coin_list_service.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025)
# Описание: Сервис для управления списком криптовалют с максимальной
# отказоустойчивостью, производительностью и целостностью данных.
#
# Ключевые улучшения "Distinguished Engineer":
# 1.  ПРЕДВАРИТЕЛЬНОЕ ИНДЕКСИРОВАНИЕ: Вместо медленного поиска по списку при каждом
#     запросе, сервис теперь создает в Redis быстрые поисковые индексы
#     (по ID, символу). Это снижает нагрузку и ускоряет поиск в сотни раз.
# 2.  АТОМАРНОЕ ОБНОВЛЕНИЕ КЭША: Обновление данных происходит в временном
#     ключе. Только после полной и успешной обработки данных, временный ключ
#     атомарно переименовывается в основной. Это исключает race conditions
#     и гарантирует, что пользователь никогда не получит неконсистентные данные.
# 3.  СТРОГАЯ ИЕРАРХИЯ ПОИСКА: Запрос сначала проверяется по быстрым индексам
#     (ID, символ) и только в крайнем случае используется более медленный
#     нечеткий поиск по названию.
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

from bot.config.settings import CoinListServiceConfig, EndpointsConfig
from bot.utils.models import Coin

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ClientResponseError)

class CoinListService:
    _COIN_LIST_CACHE_KEY = "cache:coin_list:v3:all"
    _COIN_MAP_CACHE_KEY = "cache:coin_list:v3:map" # Hash: id -> coin_json
    _SEARCH_SYMBOL_KEY_PREFIX = "search:coin:v3:symbol" # Hash: symbol -> id
    _SEARCH_NAME_CHOICES_KEY = "cache:coin_list:v3:name_choices" # For fuzzy search

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

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=5, logger=logger, jitter=backoff.full_jitter)
    async def _fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        logger.info(f"Загрузка свежего списка монет с API: {self._coin_list_url}")
        async with self.http_session.get(self._coin_list_url, timeout=15) as response:
            if response.status == 429:
                logger.warning("Получен статус 429 (Too Many Requests). Ожидание перед повторной попыткой.")
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
        logger.info("Запуск полного обновления списка монет и поисковых индексов.")
        coin_data = None
        try:
            coin_data = await self._fetch_from_api()
        except Exception as e:
            logger.error(f"Загрузка с API не удалась после всех попыток: {e}", exc_info=True)

        if not coin_data:
            coin_data = await self._load_fallback_data()

        if not coin_data:
            logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Не удалось обновить список монет ни с API, ни из резервного файла.")
            return

        try:
            coins = [Coin.model_validate(c) for c in coin_data]
            
            # Начинаем транзакцию для атомарного обновления
            pipe = self.redis.pipeline()
            
            # Временные ключи, чтобы не затронуть старые данные во время обновления
            temp_coin_map_key = f"{self._COIN_MAP_CACHE_KEY}:temp"
            temp_symbol_map_key = f"{self._SEARCH_SYMBOL_KEY_PREFIX}:temp"
            temp_name_choices_key = f"{self._SEARCH_NAME_CHOICES_KEY}:temp"

            # Очищаем временные ключи перед записью
            pipe.delete(temp_coin_map_key, temp_symbol_map_key, temp_name_choices_key)

            # Готовим данные для индексов
            coin_map_to_cache = {c.id: c.model_dump_json() for c in coins}
            symbol_map_to_cache = {c.symbol.lower(): c.id for c in coins}
            name_choices_to_cache = {c.name: c.id for c in coins}

            # Заполняем временные индексы
            if coin_map_to_cache:
                pipe.hset(temp_coin_map_key, mapping=coin_map_to_cache)
            if symbol_map_to_cache:
                pipe.hset(temp_symbol_map_key, mapping=symbol_map_to_cache)
            if name_choices_to_cache:
                # Для нечеткого поиска храним как единый JSON
                pipe.set(temp_name_choices_key, json.dumps(name_choices_to_cache))

            # Атомарно переименовываем временные ключи в основные
            pipe.rename(temp_coin_map_key, self._COIN_MAP_CACHE_KEY)
            pipe.rename(temp_symbol_map_key, self._SEARCH_SYMBOL_KEY_PREFIX)
            pipe.rename(temp_name_choices_key, self._SEARCH_NAME_CHOICES_KEY)
            
            # Выполняем все команды в одной транзакции
            await pipe.execute()
            
            logger.info(f"Успешно обновлено и проиндексировано {len(coins)} монет.")

        except ValidationError as e:
            logger.error(f"Ошибка валидации данных монет: {e}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при кэшировании и индексации данных: {e}")

    async def find_coin_by_query(self, query: str) -> Optional[Coin]:
        query_lower = query.lower().strip()
        if not query_lower:
            return None

        # 1. Сначала ищем по символу (самый частый случай)
        found_id = await self.redis.hget(self._SEARCH_SYMBOL_KEY_PREFIX, query_lower)
        
        # 2. Если не нашли, ищем по ID (второй по частоте случай)
        if not found_id:
            # Проверяем, существует ли такой ID напрямую в нашей карте монет
            if await self.redis.hexists(self._COIN_MAP_CACHE_KEY, query_lower):
                found_id = query_lower

        # 3. Если нашли ID одним из быстрых способов, получаем полную информацию о монете
        if found_id:
            coin_json = await self.redis.hget(self._COIN_MAP_CACHE_KEY, found_id)
            if coin_json:
                return Coin.model_validate_json(coin_json)

        # 4. Если быстрые методы не сработали, используем нечеткий поиск по названию
        name_choices_json = await self.redis.get(self._SEARCH_NAME_CHOICES_KEY)
        if not name_choices_json:
            logger.warning("Кэш для нечеткого поиска имен пуст. Возможно, требуется обновление.")
            return None
            
        name_choices = json.loads(name_choices_json)
        best_match = process.extractOne(query_lower, name_choices.keys(), scorer=fuzz.WRatio, score_cutoff=self.config.search_score_cutoff)
        
        if best_match:
            found_name, score, _ = best_match
            found_id_by_name = name_choices[found_name]
            coin_json = await self.redis.hget(self._COIN_MAP_CACHE_KEY, found_id_by_name)
            if coin_json:
                logger.info(f"Найдена монета через нечеткий поиск: '{query}' -> '{found_name}' со счетом {score:.2f}")
                return Coin.model_validate_json(coin_json)

        logger.warning(f"Монета по запросу '{query}' не найдена ни одним из методов.")
        return None
