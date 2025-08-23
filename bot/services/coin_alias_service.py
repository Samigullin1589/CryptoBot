# bot/services/coin_alias_service.py
# Дата обновления: 23.08.2025
# Версия: 2.1.0
# Описание: Сервис для работы с псевдонимами тикеров криптовалют.

import json
import time
from pathlib import Path
from typing import Dict, Optional

from loguru import logger
from redis.asyncio import Redis

from bot.utils.keys import KeyFactory

class CoinAliasService:
    """
    Сервис для разрешения псевдонимов криптовалют (например, "эфир" -> "ethereum").
    """
    _cache: Optional[Dict[str, str]] = None
    _cache_load_time: float = 0.0

    def __init__(self, redis_client: Redis):
        """Инициализирует сервис с зависимостями."""
        self.redis = redis_client
        self.keys = KeyFactory
        self.aliases_file_path = Path(__file__).parent.parent.parent / "data" / "ticker_aliases.json"
        logger.info("Сервис CoinAliasService инициализирован.")

    async def _load_aliases_if_needed(self) -> Dict[str, str]:
        """Загружает карту псевдонимов, используя стратегию "cache-aside"."""
        if self._cache is not None and (time.monotonic() - self._cache_load_time) < 3600:
            return self._cache

        try:
            cached_map_json = await self.redis.get(self.keys.coin_aliases_map())
            if cached_map_json:
                self._cache = json.loads(cached_map_json)
                self._cache_load_time = time.monotonic()
                return self._cache
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша псевдонимов из Redis: {e}")

        alias_map = self._load_from_fallback_file()
        
        try:
            await self.redis.set(self.keys.coin_aliases_map(), json.dumps(alias_map), ex=86400)
        except Exception as e:
            logger.error(f"Не удалось сохранить кэш псевдонимов в Redis: {e}")

        self._cache = alias_map
        self._cache_load_time = time.monotonic()
        logger.info(f"Загружено и закэшировано {len(self._cache)} псевдонимов из файла.")
        return self._cache

    def _load_from_fallback_file(self) -> Dict[str, str]:
        """Синхронно читает JSON-файл с псевдонимами."""
        if not self.aliases_file_path.exists(): return {}
        try:
            with open(self.aliases_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            alias_map: Dict[str, str] = {}
            for ticker, info in data.get("aliases", {}).items():
                coingecko_id = info.get("coingecko_id")
                if not coingecko_id: continue
                
                alias_map[ticker.lower()] = coingecko_id
                for alias in info.get("aliases", []):
                    alias_map[alias.lower()] = coingecko_id
            return alias_map
        except Exception as e:
            logger.exception(f"Не удалось загрузить файл псевдонимов: {e}")
        return {}

    async def resolve_alias(self, query: str) -> str:
        """Преобразует псевдоним в канонический ID."""
        query_lower = query.lower().strip()
        alias_map = await self._load_aliases_if_needed()
        return alias_map.get(query_lower, query_lower)

    async def reload_aliases(self) -> int:
        """Принудительно перезагружает псевдонимы из файла в кэш."""
        self._cache = None
        await self.redis.delete(self.keys.coin_aliases_map())
        await self._load_aliases_if_needed()
        return len(self._cache) if self._cache else 0