# ===============================================================
# Файл: bot/services/price_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Сервис для получения цен на криптовалюты. Полностью
# переработан для интеграции с "умным" CoinListService и
# использования CoinGecko как единого, надежного источника данных.
# ===============================================================

import logging
import json
from typing import Optional

import aiohttp
import redis.asyncio as redis

from bot.config.settings import settings
from bot.utils.models import PriceInfo
from bot.services.coin_list_service import CoinListService
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class PriceService:
    """
    Сервис для получения цен на криптовалюты с кэшированием в Redis.
    Использует CoinListService для поиска монет и CoinGecko для получения данных.
    """
    def __init__(
        self, 
        coin_list_service: CoinListService, 
        redis_client: redis.Redis, 
        http_session: aiohttp.ClientSession
    ):
        self.coin_list_service = coin_list_service
        self.redis = redis_client
        self.session = http_session

    async def get_crypto_price(self, query: str) -> Optional[PriceInfo]:
        """
        Получает цену криптовалюты, используя кэш и CoinGecko API.

        :param query: Запрос пользователя (например, "btc", "эфир", "bitcoin").
        :return: Pydantic-модель PriceInfo или None, если монета не найдена.
        """
        # --- Шаг 1: Нормализация запроса и поиск монеты через CoinListService ---
        normalized_query = settings.app.ticker_aliases.get(query.strip().lower(), query.strip().lower())
        
        # Интеллектуальный поиск монеты по ее ID, символу или названию
        coin_info = await self.coin_list_service.find_coin(normalized_query)
        if not coin_info:
            logger.warning(f"Coin '{normalized_query}' not found by CoinListService.")
            return None

        # --- Шаг 2: Проверка кэша в Redis ---
        cache_key = f"price_cache:{coin_info.id}"
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for '{coin_info.id}'.")
            return PriceInfo.model_validate_json(cached_data)

        # --- Шаг 3: Если в кэше нет, делаем запрос к CoinGecko API ---
        logger.info(f"Cache miss for '{coin_info.id}'. Fetching from CoinGecko.")
        url = (
            f"{settings.api_endpoints.coingecko_api_base}/coins/markets"
            f"?vs_currency=usd&ids={coin_info.id}"
        )
        market_data_list = await make_request(self.session, url)

        if not (market_data_list and isinstance(market_data_list, list)):
            logger.error(f"Failed to fetch market data for '{coin_info.id}' from CoinGecko.")
            return None
        
        market_data = market_data_list[0]
        
        # --- Шаг 4: Создаем модель PriceInfo и кэшируем результат ---
        try:
            price_info = PriceInfo(
                id=market_data['id'],
                symbol=market_data['symbol'].upper(),
                name=market_data['name'],
                price=market_data['current_price'],
                price_change_24h=market_data.get('price_change_percentage_24h'),
                algorithm=coin_info.algorithm # Добавляем алгоритм из нашего справочника
            )
            
            # Кэшируем успешный результат на 2 минуты
            await self.redis.set(cache_key, price_info.model_dump_json(), ex=120)
            logger.info(f"Successfully fetched and cached price for '{coin_info.id}'.")
            
            return price_info
            
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing CoinGecko market data for '{coin_info.id}': {e}")
            return None

