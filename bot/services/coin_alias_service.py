# bot/services/coin_alias_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Высокопроизводительный сервис для работы с псевдонимами (алиасами)
# тикеров криптовалют с многоуровневым кэшированием.

import json
import time
from pathlib import Path
from typing import Dict, Optional

from loguru import logger
from redis.asyncio import Redis

from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory


class CoinAliasService:
    """
    Сервис для разрешения псевдонимов криптовалют (например, "эфир" -> "ethereum").
    Использует in-memory кэш для мгновенного доступа, который синхронизируется
    с Redis и резервным JSON-файлом.
    """
    _cache: Optional[Dict[str, str]] = None
    _cache_load_time: float = 0.0

    def __init__(self):
        """Инициализирует сервис, получая зависимости из централизованного источника."""
        self.redis: Redis = get_redis_client()
        self.keys = KeyFactory
        # Путь к файлу с псевдонимами определяется относительно корня проекта
        self.aliases_file_path = Path(__file__).parent.parent.parent / "data" / "ticker_aliases.json"
        logger.info("Сервис CoinAliasService инициализирован.")

    async def _load_aliases_if_needed(self) -> Dict[str, str]:
        """
        Загружает карту псевдонимов, используя стратегию "cache-aside".
        1. Проверяет быстрый in-memory кэш.
        2. Если его нет, проверяет кэш в Redis.
        3. Если и там нет, загружает из файла, сохраняет в Redis и в in-memory кэш.
        """
        # 1. Проверка in-memory кэша
        if self._cache is not None and (time.monotonic() - self._cache_load_time) < 3600: # Кэш в памяти живет 1 час
            return self._cache

        # 2. Проверка кэша в Redis
        try:
            cached_map_json = await self.redis.get(self.keys.coin_aliases_map())
            if cached_map_json:
                self._cache = json.loads(cached_map_json)
                self._cache_load_time = time.monotonic()
                logger.debug(f"Загружено {len(self._cache)} псевдонимов из кэша Redis.")
                return self._cache
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша псевдонимов из Redis: {e}")

        # 3. Загрузка из файла
        logger.warning("Кэш псевдонимов в Redis не найден или поврежден. Загрузка из файла.")
        alias_map = self._load_from_fallback_file()
        
        # Сохраняем в Redis на длительный срок
        try:
            await self.redis.set(self.keys.coin_aliases_map(), json.dumps(alias_map), ex=86400) # 24 часа
        except Exception as e:
            logger.error(f"Не удалось сохранить кэш псевдонимов в Redis: {e}")

        self._cache = alias_map
        self._cache_load_time = time.monotonic()
        logger.info(f"Успешно загружено и закэшировано {len(self._cache)} псевдонимов из файла.")
        return self._cache

    def _load_from_fallback_file(self) -> Dict[str, str]:
        """Синхронно читает и парсит JSON-файл с псевдонимами."""
        if not self.aliases_file_path.exists():
            logger.error(f"Файл псевдонимов не найден по пути: {self.aliases_file_path}")
            return {}
            
        try:
            with open(self.aliases_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            alias_map: Dict[str, str] = {}
            for ticker, info in data.get("aliases", {}).items():
                coingecko_id = info.get("coingecko_id")
                if not coingecko_id:
                    continue
                
                # Добавляем основной тикер и все его псевдонимы
                alias_map[ticker.lower()] = coingecko_id
                for alias in info.get("aliases", []):
                    alias_map[alias.lower()] = coingecko_id
            return alias_map
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в файле псевдонимов {self.aliases_file_path}: {e}")
        except Exception as e:
            logger.exception(f"Не удалось загрузить или обработать файл псевдонимов: {e}")
        return {}

    async def resolve_alias(self, query: str) -> str:
        """
        Преобразует псевдоним (например, 'btc') в канонический ID ('bitcoin').
        Если псевдоним не найден, возвращает исходный запрос в нижнем регистре.
        """
        query_lower = query.lower().strip()
        alias_map = await self._load_aliases_if_needed()
        return alias_map.get(query_lower, query_lower)

    async def reload_aliases(self) -> int:
        """
        Принудительно перезагружает псевдонимы из файла в кэш.
        Предназначен для вызова администратором.
        """
        logger.info("Принудительная перезагрузка псевдонимов из файла...")
        self._cache = None # Сбрасываем in-memory кэш
        await self.redis.delete(self.keys.coin_aliases_map()) # Удаляем из Redis
        await self._load_aliases_if_needed() # Загружаем заново
        return len(self._cache) if self._cache else 0