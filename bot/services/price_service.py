# bot/services/price_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Высокопроизводительный сервис для получения и кэширования цен
# на криптовалюты, работающий как отказоустойчивый слой поверх MarketDataService.

import asyncio
import json
import time
from typing import Dict, Iterable, List, Optional

from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.market_data_service import MarketDataService
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory


class PriceData(BaseModel):
    """
    Pydantic-модель для хранения цены и временной метки в кэше.
    Обеспечивает целостность и предсказуемость данных.
    """
    price: float
    timestamp: int


class PriceService:
    """
    Предоставляет быстрый доступ к ценам криптовалют, управляя
    многоуровневым кэшированием (in-memory и Redis) и делегируя
    запросы на получение свежих данных в MarketDataService.
    """

    def __init__(self, market_data_service: MarketDataService):
        """
        Инициализирует сервис с необходимыми зависимостями.

        :param market_data_service: Сервис для получения рыночных данных.
        """
        self.redis: Redis = get_redis_client()
        self.market_data_service = market_data_service
        self.config = settings.PRICE
        self.keys = KeyFactory
        logger.info("Сервис PriceService инициализирован.")

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """
        Получает цены для списка ID монет. Сначала проверяет кэш,
        затем одним пакетным запросом получает недостающие данные.
        """
        if not coin_ids:
            return {}

        # 1. Проверяем кэш для всех запрошенных монет
        cached_prices = await self._get_cached_prices(coin_ids)
        
        # 2. Определяем, для каких монет данных в кэше нет
        missing_ids = [cid for cid, price in cached_prices.items() if price is None]

        # 3. Если есть пропуски, запрашиваем их одним пакетом
        if missing_ids:
            logger.debug(f"Промах кэша для {len(missing_ids)} монет. Запрашиваю свежие данные...")
            fresh_prices = await self.market_data_service.get_prices(missing_ids)
            
            # Кэшируем новые данные
            await self._cache_prices(fresh_prices)
            
            # Обновляем наш итоговый словарь
            cached_prices.update(fresh_prices)

        return cached_prices

    async def get_price(self, coin_id: str) -> Optional[float]:
        """Получает цену для одной монеты."""
        prices = await self.get_prices([coin_id])
        return prices.get(coin_id)

    async def prefetch_top_coins(self):
        """
        "Прогревает" кэш, запрашивая и сохраняя цены для самых
        популярных криптовалют по рыночной капитализации.
        """
        logger.info("Запуск задачи 'прогрева' кэша цен...")
        try:
            top_coins = await self.market_data_service.get_top_coins_by_market_cap(
                limit=self.config.PREFETCH_COIN_LIMIT
            )
            if not top_coins:
                logger.warning("Не удалось получить список топ-монет для 'прогрева' кэша.")
                return

            top_coin_ids = [coin.id for coin in top_coins]
            await self.get_prices(top_coin_ids)
            logger.success(f"Кэш цен для {len(top_coin_ids)} топ-монет успешно 'прогрет'.")
        except Exception as e:
            logger.exception(f"Ошибка во время 'прогрева' кэша цен: {e}")

    async def _get_cached_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Массово получает цены из кэша Redis."""
        if not self.redis:
            return {cid: None for cid in coin_ids}
        
        keys = [self.keys.price_cache(cid) for cid in coin_ids]
        try:
            cached_results = await self.redis.mget(keys)
            
            prices: Dict[str, Optional[float]] = {}
            now = int(time.time())

            for coin_id, raw_data in zip(coin_ids, cached_results):
                if raw_data:
                    try:
                        price_data = PriceData.model_validate_json(raw_data)
                        # Проверяем, не устарели ли данные в кэше
                        if (now - price_data.timestamp) <= self.config.CACHE_TTL_SECONDS:
                            prices[coin_id] = price_data.price
                            continue
                    except (ValidationError, json.JSONDecodeError):
                        logger.warning(f"Поврежденные данные в кэше для {coin_id}.")
                
                prices[coin_id] = None # Если данных нет или они устарели/повреждены
            return prices
        except Exception as e:
            logger.error(f"Ошибка при чтении цен из кэша Redis: {e}")
            return {cid: None for cid in coin_ids}

    async def _cache_prices(self, price_data: Dict[str, Optional[float]]):
        """Массово сохраняет цены в кэш Redis."""
        if not self.redis:
            return
            
        try:
            pipe = self.redis.pipeline()
            now = int(time.time())
            cached_count = 0
            for coin_id, price in price_data.items():
                if price is not None:
                    key = self.keys.price_cache(coin_id)
                    data = PriceData(price=price, timestamp=now).model_dump_json()
                    pipe.set(key, data, ex=self.config.CACHE_TTL_SECONDS)
                    cached_count += 1
            
            if cached_count > 0:
                await pipe.execute()
                logger.debug(f"Сохранено в кэш {cached_count} цен.")
        except Exception as e:
            logger.error(f"Ошибка при сохранении цен в кэш Redis: {e}")