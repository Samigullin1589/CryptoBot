# bot/services/coin_list_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Отказоустойчивый сервис для получения, кэширования и индексации
# списка криптовалют из нескольких источников.

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.dependencies import get_redis_client
from bot.utils.http_client import http_session
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

    def __init__(self):
        """Инициализирует сервис с зависимостями и конфигурацией."""
        self.redis: Redis = get_redis_client()
        self.config = settings.COIN_LIST
        self.keys = KeyFactory
        self.fallback_path = Path(__file__).parent.parent.parent / self.config.FALLBACK_FILE_PATH
        logger.info("Сервис CoinListService инициализирован.")

    async def update_coin_list(self) -> int:
        """
        Основной метод, вызываемый планировщиком. Получает, обрабатывает,
        кэширует и индексирует список монет.
        """
        logger.info("Запуск задачи обновления списка криптовалют...")
        
        # 1. Получаем данные из внешних источников
        coins = await self._fetch_from_sources()
        
        # 2. Если внешние источники недоступны, используем резервную копию
        if not coins:
            logger.warning("Не удалось получить данные из онлайн-источников. Загрузка из резервного файла.")
            coins = self._load_fallback_coins()

        if not coins:
            logger.critical("Обновление списка монет не удалось: все источники, включая резервный, недоступны.")
            return 0

        # 3. Нормализуем, дедуплицируем и валидируем данные
        validated_coins = self._normalize_and_validate(coins)
        
        # 4. Сохраняем в Redis и создаем поисковые индексы
        await self._cache_and_index_coins(validated_coins)

        # 5. Создаем свежую резервную копию
        await self._create_fallback_backup(validated_coins)

        logger.success(f"Список из {len(validated_coins)} криптовалют успешно обновлен и проиндексирован.")
        return len(validated_coins)

    async def _fetch_from_sources(self) -> List[Dict[str, str]]:
        """
        Пытается получить список монет сначала из CoinGecko (приоритет),
        затем из Binance в качестве резерва.
        """
        try:
            logger.debug("Попытка получения списка монет из CoinGecko...")
            async with http_session() as client:
                response = await client.get(self.config.COINGECKO_URL)
                response.raise_for_status()
                return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.warning(f"Ошибка при получении данных от CoinGecko: {e}. Переключаюсь на Binance.")
        
        try:
            logger.debug("Попытка получения списка монет из Binance...")
            async with http_session() as client:
                response = await client.get(self.config.BINANCE_URL)
                response.raise_for_status()
                data = response.json()
                
                # Адаптируем ответ Binance под наш формат
                unique_assets = {s['baseAsset'] for s in data.get('symbols', []) if 'baseAsset' in s}
                return [{"id": asset.lower(), "symbol": asset, "name": asset} for asset in unique_assets]
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка при получении данных от Binance: {e}")
        
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
                logger.warning(f"Ошибка валидации данных монеты: {coin_data}. Ошибка: {e}")
        
        validated_coins.sort(key=lambda c: c.symbol)
        return validated_coins[:self.config.MAX_ITEMS]

    async def _cache_and_index_coins(self, coins: List[CoinData]):
        """Сохраняет список монет и создает поисковые индексы в Redis."""
        try:
            pipe = self.redis.pipeline()
            
            # 1. Сохраняем полный список как одну JSON-строку
            coins_json = json.dumps([c.model_dump() for c in coins], ensure_ascii=False)
            pipe.set(self.keys.coin_list(), coins_json, ex=self.config.CACHE_TTL_SECONDS)
            
            # 2. Создаем индексы для быстрого поиска: symbol -> id и id -> symbol
            # Используем HASH для хранения всех индексов в одном месте
            symbol_to_id_map = {c.symbol.upper(): c.id for c in coins}
            id_to_symbol_map = {c.id: c.symbol.upper() for c in coins}
            
            pipe.delete(self.keys.coin_index_symbol_to_id())
            pipe.delete(self.keys.coin_index_id_to_symbol())
            
            if symbol_to_id_map:
                pipe.hset(self.keys.coin_index_symbol_to_id(), mapping=symbol_to_id_map)
            if id_to_symbol_map:
                pipe.hset(self.keys.coin_index_id_to_symbol(), mapping=id_to_symbol_map)

            await pipe.execute()
        except Exception as e:
            logger.exception(f"Ошибка при кэшировании или индексации списка монет в Redis: {e}")

    async def get_all_coins(self) -> List[CoinData]:
        """Возвращает полный список монет из кэша Redis."""
        try:
            coins_json = await self.redis.get(self.keys.coin_list())
            if coins_json:
                return [CoinData.model_validate(c) for c in json.loads(coins_json)]
        except Exception as e:
            logger.error(f"Ошибка при получении списка монет из кэша Redis: {e}")
        
        # Если Redis недоступен, возвращаем данные из файла
        return [CoinData.model_validate(c) for c in self._load_fallback_coins()]

    async def get_coin_id_by_ticker(self, ticker: str) -> Optional[str]:
        """Быстро находит ID монеты (например, 'bitcoin') по ее тикеру ('BTC')."""
        try:
            return await self.redis.hget(self.keys.coin_index_symbol_to_id(), ticker.upper())
        except Exception as e:
            logger.error(f"Ошибка Redis при поиске ID для тикера {ticker}: {e}")
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
            
            # Асинхронно записываем в файл, чтобы не блокировать основной поток
            def _write_sync():
                with open(self.fallback_path, 'w', encoding='utf-8') as f:
                    json.dump(coins_dict, f, ensure_ascii=False, indent=2)
            
            await asyncio.to_thread(_write_sync)
            logger.info(f"Резервная копия списка монет успешно создана в {self.fallback_path}")
        except Exception as e:
            logger.error(f"Не удалось создать резервную копию списка монет: {e}")