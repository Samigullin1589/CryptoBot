# src/bot/services/price_service.py
import json
import time
from typing import Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from bot.config.settings import PriceServiceConfig
from bot.services.market_data_service import MarketDataService
from bot.utils.keys import KeyFactory


class PriceData(BaseModel):
    """Pydantic-модель для хранения цены и временной метки в кэше."""
    price: float
    timestamp: int


class PriceService:
    """Сервис для управления ценами криптовалют с кэшированием."""

    def __init__(
        self,
        redis_client: Redis,
        market_data_service: MarketDataService,
        config: PriceServiceConfig,
    ):
        self.redis = redis_client
        self.market_data_service = market_data_service
        self.config = config
        self.keys = KeyFactory
        logger.info("Сервис PriceService инициализирован.")

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Получает цены для списка ID монет."""
        if not coin_ids:
            return {}

        try:
            cached_prices = await self._get_cached_prices(coin_ids)
            missing_ids = [cid for cid, price in cached_prices.items() if price is None]

            if missing_ids:
                logger.debug(f"Промах кэша для {len(missing_ids)} монет. Запрашиваю свежие данные...")
                fresh_prices = await self.market_data_service.get_prices(missing_ids)
                
                if fresh_prices:
                    await self._cache_prices(fresh_prices)
                    cached_prices.update(fresh_prices)
                else:
                    logger.warning("MarketDataService вернул пустой результат")

            return cached_prices
        except Exception as e:
            logger.exception(f"Критическая ошибка в get_prices: {e}")
            return {cid: None for cid in coin_ids}

    async def get_price(self, coin_id: str) -> Optional[float]:
        """Получает цену для одной монеты."""
        if not coin_id:
            return None
        try:
            prices = await self.get_prices([coin_id])
            return prices.get(coin_id)
        except Exception as e:
            logger.exception(f"Ошибка получения цены для {coin_id}: {e}")
            return None

    async def prefetch_top_coins(self):
        """Прогревает кэш для топ криптовалют."""
        logger.info("Запуск задачи 'прогрева' кэша цен...")
        try:
            top_coins = await self.market_data_service.get_top_n_coins(
                limit=self.config.top_n_coins
            )
            if not top_coins:
                logger.warning("Не удалось получить список топ-монет для 'прогрева' кэша.")
                return

            top_coin_ids = [coin['id'] for coin in top_coins if coin.get('id')]
            if top_coin_ids:
                await self.get_prices(top_coin_ids)
                logger.success(f"Кэш цен для {len(top_coin_ids)} топ-монет успешно 'прогрет'.")
        except Exception as e:
            logger.exception(f"Ошибка во время 'прогрева' кэша цен: {e}")

    async def _get_cached_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Массово получает цены из кэша Redis."""
        keys = [self.keys.get_coin_price_key(cid) for cid in coin_ids]
        try:
            cached_results = await self.redis.mget(keys)
            
            prices: Dict[str, Optional[float]] = {}
            now = int(time.time())

            for coin_id, raw_data in zip(coin_ids, cached_results):
                if raw_data:
                    try:
                        price_data = PriceData.model_validate_json(raw_data)
                        if (now - price_data.timestamp) <= self.config.cache_ttl_seconds:
                            prices[coin_id] = price_data.price
                            continue
                    except (ValidationError, json.JSONDecodeError) as e:
                        logger.warning(f"Поврежденные данные в кэше для {coin_id}: {e}")
                
                prices[coin_id] = None
            return prices
        except Exception as e:
            logger.exception(f"Ошибка при чтении цен из кэша Redis: {e}")
            return {cid: None for cid in coin_ids}

    async def _cache_prices(self, price_data: Dict[str, Optional[float]]):
        """Массово сохраняет цены в кэш Redis."""
        if not price_data:
            return
            
        try:
            pipe = self.redis.pipeline()
            now = int(time.time())
            cached_count = 0
            
            for coin_id, price in price_data.items():
                if price is not None and isinstance(price, (int, float)):
                    key = self.keys.get_coin_price_key(coin_id)
                    data = PriceData(price=float(price), timestamp=now).model_dump_json()
                    pipe.set(key, data, ex=self.config.cache_ttl_seconds)
                    cached_count += 1
            
            if cached_count > 0:
                await pipe.execute()
                logger.debug(f"Сохранено в кэш {cached_count} цен.")
        except Exception as e:
            logger.exception(f"Ошибка при сохранении цен в кэш Redis: {e}")