# src/bot/services/coin_list_service.py
# =================================================================================
# Файл: bot/services/coin_list_service.py
# Версия: "Distinguished Engineer" — ФИНАЛЬНАЯ СБОРКА
# Описание:
#   • Объединяет вашу превосходную логику (отказоустойчивость, индексация,
#     Pydantic-валидация, самообновляемый fallback) с DI-паттерном.
#   • Зависимости (redis, http_client, config) теперь передаются
#     через конструктор, что делает сервис полностью тестируемым.
#   • Убраны устаревшие импорты.
# =================================================================================
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from bot.config.settings import CoinListServiceConfig
from bot.utils.http_client import HttpClient
from bot.utils.keys import KeyFactory


class CoinData(BaseModel):
    """
    Pydantic-модель для валидации данных о монете.
    Гарантирует консистентность структуры данных по всему приложению.
    """
    id: str
    symbol: str
    name: str


class CoinListService:
    """
    Агрегирует списки криптовалют из внешних API, управляет кэшем в Redis
    и предоставляет быстрый доступ к данным для других сервисов.
    """

    def __init__(
        self,
        redis_client: Redis,
        http_client: HttpClient,
        config: CoinListServiceConfig,
    ):
        """Инициализирует сервис с зависимостями и конфигурацией."""
        self.redis = redis_client
        self.http_client = http_client
        self.config = config
        self.keys = KeyFactory
        # Путь к fallback-файлу теперь строится относительно корня проекта
        self.fallback_path = Path(self.config.fallback_file_path)
        logger.info("Сервис CoinListService инициализирован.")

    async def update_coin_list(self) -> int:
        """
        Основной метод, вызываемый планировщиком. Получает, обрабатывает,
        кэширует и индексирует список монет.
        """
        logger.info("Запуск задачи обновления списка криптовалют...")
        
        coins = await self._fetch_from_sources()
        
        if not coins:
            logger.warning("Не удалось получить данные из онлайн-источников. Загрузка из резервного файла.")
            coins = self._load_fallback_coins()

        if not coins:
            logger.critical("Обновление списка монет не удалось: все источники, включая резервный, недоступны.")
            return 0

        validated_coins = self._normalize_and_validate(coins)
        
        await self._cache_and_index_coins(validated_coins)
        await self._create_fallback_backup(validated_coins)

        logger.success(f"Список из {len(validated_coins)} криптовалют успешно обновлен и проиндексирован.")
        return len(validated_coins)

    async def _fetch_from_sources(self) -> List[Dict[str, str]]:
        """
        Пытается получить список монет из CoinGecko.
        """
        logger.debug("Попытка получения списка монет из CoinGecko...")
        try:
            url = f"{self.http_client.config.coingecko_api_base}{self.http_client.config.coins_list_endpoint}"
            data = await self.http_client.get(url)
            if data and isinstance(data, list):
                return data
        except Exception as e:
            logger.warning(f"Ошибка при получении данных от CoinGecko: {e}.")
        
        return []

    def _normalize_and_validate(self, coins: List[Dict[str, str]]) -> List[CoinData]:
        """
        Приводит данные к единому формату, удаляет дубликаты по символу
        и валидирует каждую запись с помощью Pydantic.
        """
        seen_symbols = set()
        validated_coins = []
        for coin_data in coins:
            try:
                coin = CoinData.model_validate(coin_data)
                symbol_upper = coin.symbol.upper()
                if symbol_upper not in seen_symbols:
                    validated_coins.append(coin)
                    seen_symbols.add(symbol_upper)
            except ValidationError as e:
                logger.trace(f"Ошибка валидации данных монеты: {coin_data}. Ошибка: {e}")
        
        validated_coins.sort(key=lambda c: c.symbol)
        return validated_coins

    async def _cache_and_index_coins(self, coins: List[CoinData]):
        """Сохраняет список монет и создает поисковые индексы в Redis."""
        try:
            pipe = self.redis.pipeline()
            
            coins_json = json.dumps([c.model_dump() for c in coins], ensure_ascii=False)
            pipe.set(self.keys.get_coin_list_key(), coins_json)
            
            symbol_to_id_map = {c.symbol.upper(): c.id for c in coins}
            id_to_symbol_map = {c.id: c.symbol.upper() for c in coins}
            
            # Очищаем старые HASH-таблицы перед записью новых
            pipe.delete(self.keys.get_coin_index_symbol_to_id_key())
            pipe.delete(self.keys.get_coin_index_id_to_symbol_key())
            
            if symbol_to_id_map:
                pipe.hset(self.keys.get_coin_index_symbol_to_id_key(), mapping=symbol_to_id_map)
            if id_to_symbol_map:
                pipe.hset(self.keys.get_coin_index_id_to_symbol_key(), mapping=id_to_symbol_map)

            await pipe.execute()
        except Exception as e:
            logger.exception(f"Ошибка при кэшировании или индексации списка монет в Redis: {e}")

    async def get_coin_list(self) -> List[CoinData]:
        """Возвращает полный список монет из кэша Redis или fallback."""
        try:
            coins_json = await self.redis.get(self.keys.get_coin_list_key())
            if coins_json:
                return [CoinData.model_validate(c) for c in json.loads(coins_json)]
        except Exception as e:
            logger.error(f"Ошибка при получении списка монет из кэша Redis: {e}")
        
        logger.warning("Не удалось получить список монет из Redis, используем fallback.")
        fallback_data = self._load_fallback_coins()
        return [CoinData.model_validate(c) for c in fallback_data]

    async def get_coin_id_by_symbol(self, symbol: str) -> Optional[str]:
        """Быстро находит ID монеты (например, 'bitcoin') по ее символу ('BTC')."""
        try:
            coin_id = await self.redis.hget(self.keys.get_coin_index_symbol_to_id_key(), symbol.upper())
            return coin_id
        except Exception as e:
            logger.error(f"Ошибка Redis при поиске ID для символа {symbol}: {e}")
            return None

    async def get_symbol_by_coin_id(self, coin_id: str) -> Optional[str]:
        """Быстро находит символ монеты ('BTC') по ее ID ('bitcoin')."""
        try:
            symbol = await self.redis.hget(self.keys.get_coin_index_id_to_symbol_key(), coin_id)
            return symbol
        except Exception as e:
            logger.error(f"Ошибка Redis при поиске символа для ID {coin_id}: {e}")
            return None

    def _load_fallback_coins(self) -> List[Dict[str, str]]:
        """Загружает список монет из локального резервного JSON-файла."""
        if not self.fallback_path.exists():
            logger.error(f"Резервный файл {self.fallback_path} не найден.")
            return []
        try:
            with open(self.fallback_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f"Не удалось загрузить или обработать резервный файл монет: {e}")
            return []

    async def _create_fallback_backup(self, coins: List[CoinData]):
        """Создает локальную резервную копию списка монет."""
        try:
            coins_dict = [c.model_dump() for c in coins]
            
            def _write_sync():
                self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.fallback_path, 'w', encoding='utf-8') as f:
                    json.dump(coins_dict, f, ensure_ascii=False, indent=2)
            
            await asyncio.to_thread(_write_sync)
            logger.info(f"Резервная копия списка монет успешно создана в {self.fallback_path}")
        except Exception as e:
            logger.error(f"Не удалось создать резервную копию списка монет: {e}")