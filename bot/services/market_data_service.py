# bot/services/price_service.py
# =================================================================================
# Файл: bot/services/price_service.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Сервис для получения цен на криптовалюты.
# ИСПРАВЛЕНИЕ: Метод get_prices теперь корректно использует валюту по умолчанию
# из файла конфигурации, решая ошибку 'Missing parameter vs_currencies'.
# =================================================================================

import logging
from typing import Dict, List, Optional

import aiohttp
from redis.asyncio import Redis

# Зависимости передаются через DI-контейнер
from bot.config.settings import Settings
from bot.services.coin_list_service import CoinListService

logger = logging.getLogger(__name__)

class PriceService:
    """
    Отвечает за получение и кэширование цен на криптовалюты.
    """
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        coin_list_service: CoinListService,
        settings: Settings,
    ):
        self.redis = redis
        self.http_session = http_session
        self.coin_list_service = coin_list_service
        self.settings = settings
        # URL и параметры берутся из единого объекта настроек
        self._price_url = str(self.settings.api_config.price_endpoint_url)
        self._default_currency = self.settings.tracking_defaults.default_vs_currency
        self._cache_ttl = self.settings.tracking_defaults.cache_ttl_seconds

    def _get_cache_key(self, coin_id: str, vs_currency: str) -> str:
        """Генерирует консистентный ключ для кэша цены монеты."""
        return f"cache:price:{coin_id}:{vs_currency}"

    async def get_prices(self, coin_ids: List[str], vs_currency: Optional[str] = None) -> Dict[str, Optional[float]]:
        """
        Получает цены для списка ID монет.
        Сначала проверяет кэш, затем запрашивает недостающие цены у API.
        """
        # ИСПРАВЛЕНИЕ: Если валюта не указана в вызове, используется
        # значение по умолчанию из файла конфигурации.
        target_currency = vs_currency or self._default_currency
        
        prices: Dict[str, Optional[float]] = {}
        coins_to_fetch: List[str] = []

        # Проверяем кэш для каждой монеты
        for coin_id in coin_ids:
            cache_key = self._get_cache_key(coin_id, target_currency)
            cached_price = await self.redis.get(cache_key)
            if cached_price:
                prices[coin_id] = float(cached_price)
            else:
                coins_to_fetch.append(coin_id)

        if not coins_to_fetch:
            return prices

        logger.info(f"Запрос цен с API для: {coins_to_fetch} в {target_currency}")
        
        # ИСПРАВЛЕНИЕ: Параметр 'vs_currencies' теперь всегда корректно добавляется в запрос.
        params = {
            'ids': ','.join(coins_to_fetch),
            'vs_currencies': target_currency
        }
        
        try:
            async with self.http_session.get(self._price_url, params=params) as response:
                response.raise_for_status()
                api_data = await response.json()

                for coin_id in coins_to_fetch:
                    price_data = api_data.get(coin_id)
                    price = price_data.get(target_currency) if price_data else None
                    
                    if price is not None:
                        prices[coin_id] = float(price)
                        cache_key = self._get_cache_key(coin_id, target_currency)
                        await self.redis.set(cache_key, price, ex=self._cache_ttl)
                    else:
                        prices[coin_id] = None
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при получении цен: {e}")
            for coin_id in coins_to_fetch:
                prices[coin_id] = None

        return prices

# =================================================================================
# bot/services/market_data_service.py
# =================================================================================
# Файл: bot/services/market_data_service.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Сервис для получения рыночных данных (топ монет и т.д.).
# ИСПРАВЛЕНИЕ: Метод get_top_coins_by_market_cap теперь корректно использует
# валюту по умолчанию, решая ошибку 'Missing parameter vs_currencies'.
# =================================================================================

import logging
from typing import List, Optional, Dict, Any

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import Settings

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Отвечает за получение общих рыночных данных, таких как топ монет.
    """
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        settings: Settings,
    ):
        self.redis = redis
        self.http_session = http_session
        self.settings = settings
        # URL и параметры берутся из единого объекта настроек
        self._market_data_url = str(self.settings.api_config.market_data_endpoint_url)
        self._default_currency = self.settings.tracking_defaults.default_vs_currency
        self._top_n = self.settings.update_policy.top_n_by_market_cap

    async def get_top_coins_by_market_cap(self) -> Optional[List[Dict[str, Any]]]:
        """Загружает топ-N монет по рыночной капитализации."""
        
        # ИСПРАВЛЕНИЕ: Параметр 'vs_currency' теперь всегда корректно добавляется в запрос.
        params = {
            'vs_currency': self._default_currency,
            'order': 'market_cap_desc',
            'per_page': self._top_n,
            'page': 1,
            'sparkline': 'false',
            'price_change_percentage': '1h,24h,7d'
        }
        
        logger.info(f"Запрос топ-{self._top_n} монет с API: {self._market_data_url}")
        try:
            async with self.http_session.get(self._market_data_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Успешно загружено {len(data)} монет с API.")
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при загрузке рыночных данных: {e}")
            return None

