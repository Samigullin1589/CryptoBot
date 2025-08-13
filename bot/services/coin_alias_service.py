# ===============================================================
# Файл: bot/services/coin_alias_service.py (НОВЫЙ ФАЙЛ)
# Описание: Сервис для работы с псевдонимами тикеров,
#           позволяющий находить монеты по нестандартным именам.
# ===============================================================

import logging
import json
from typing import Dict, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

class CoinAliasService:
    """Сервис для разрешения псевдонимов (алиасов) криптовалют."""
    
    _ALIAS_MAP_CACHE_KEY = "cache:coin_aliases:v1:map"
    _FALLBACK_FILE_PATH = "data/ticker_aliases.json"

    def __init__(self, redis: redis.Redis):
        self.redis = redis
        self._cache: Optional[Dict[str, str]] = None

    async def _load_aliases(self) -> Dict[str, str]:
        """Загружает карту псевдонимов из Redis или файла."""
        if self._cache:
            return self._cache

        cached_map = await self.redis.get(self._ALIAS_MAP_CACHE_KEY)
        if cached_map:
            self._cache = json.loads(cached_map)
            return self._cache

        logger.warning(f"Кэш псевдонимов не найден. Загрузка из файла {self._FALLBACK_FILE_PATH}")
        alias_map = {}
        try:
            with open(self._FALLBACK_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for ticker, info in data.get("aliases", {}).items():
                    coingecko_id = info.get("coingecko_id")
                    if not coingecko_id:
                        continue
                    # Добавляем основной тикер и все его псевдонимы
                    alias_map[ticker.lower()] = coingecko_id
                    for alias in info.get("aliases", []):
                        alias_map[alias.lower()] = coingecko_id
            
            await self.redis.set(self._ALIAS_MAP_CACHE_KEY, json.dumps(alias_map), ex=3600 * 24) # Кэш на 24 часа
            self._cache = alias_map
            logger.info(f"Успешно загружено и закэшировано {len(alias_map)} псевдонимов.")
            return alias_map
        except Exception as e:
            logger.error(f"Не удалось загрузить файл псевдонимов: {e}", exc_info=True)
            return {}

    async def resolve_alias(self, query: str) -> str:
        """
        Пытается найти CoinGecko ID по псевдониму.
        Если не находит, возвращает исходный запрос.
        """
        query_lower = query.lower().strip()
        alias_map = await self._load_aliases()
        return alias_map.get(query_lower, query_lower)