# bot/services/coin_list_service.py
# Сервис переписан для большей надёжности, использует общую http_session
# и Pydantic модели для валидации данных.

import json
import logging
from typing import List, Dict, Any, Optional

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import CoinListServiceConfig, EndpointsConfig
from bot.utils.models import Coin  # Предполагается, что у вас есть Pydantic модель Coin

logger = logging.getLogger(__name__)

class CoinListService:
    """
    Управляет получением, кэшированием и предоставлением списка криптовалют.
    """
    _COIN_LIST_CACHE_KEY = "cache:coin_list"

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
        self._coin_list_url = str(endpoints.coingecko_api_coins_list)

    async def _fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """Загружает сырой список монет с API CoinGecko."""
        logger.info(f"Загрузка свежего списка монет с API: {self._coin_list_url}")
        try:
            async with self.http_session.get(self._coin_list_url) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Успешно загружено {len(data)} монет с API.")
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при загрузке списка монет: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось декодировать JSON ответ от API списка монет: {e}")
        return None

    async def _load_fallback_data(self) -> List[Dict[str, Any]]:
        """Загружает список монет из локального резервного файла."""
        logger.warning(f"Попытка загрузить список монет из резервного файла: {self.config.fallback_file_path}")
        try:
            with open(self.config.fallback_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Успешно загружено {len(data)} монет из резервного файла.")
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Не удалось загрузить или разобрать резервный файл списка монет: {e}")
            return []

    async def update_coin_list(self) -> None:
        """
        Обновляет список монет в кэше Redis.
        Сначала пытается загрузить с API, при неудаче - из резервного файла.
        """
        logger.info("Запуск планового обновления списка монет.")
        coin_data = await self._fetch_from_api()

        if coin_data is None:
            logger.warning("Загрузка с API не удалась, попытка загрузки из резервного файла.")
            coin_data = await self._load_fallback_data()

        if coin_data:
            try:
                # Валидация данных через Pydantic модель
                coins = [Coin.model_validate(coin) for coin in coin_data]
                # Сериализуем и кэшируем валидированные данные
                coins_to_cache = [c.model_dump(mode='json') for c in coins]
                await self.redis.set(self._COIN_LIST_CACHE_KEY, json.dumps(coins_to_cache))
                logger.info(f"Успешно обновлено и кэшировано {len(coins)} монет.")
            except Exception as e:
                logger.error(f"Не удалось валидировать или кэшировать данные монет: {e}")
        else:
            logger.error("Не удалось обновить список монет ни с API, ни из резервного файла.")

    async def get_all_coins(self) -> List[Coin]:
        """
        Получает список всех монет из кэша.
        Если кэш пуст, запускает обновление.
        """
        cached_data = await self.redis.get(self._COIN_LIST_CACHE_KEY)
        if cached_data:
            try:
                coins_data = json.loads(cached_data)
                return [Coin.model_validate(c) for c in coins_data]
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Ошибка декодирования кэшированного списка монет: {e}. Запускаю обновление.")

        logger.warning("Кэш списка монет пуст или невалиден. Запускаю немедленное обновление.")
        await self.update_coin_list()

        cached_data_after_update = await self.redis.get(self._COIN_LIST_CACHE_KEY)
        if cached_data_after_update:
            return [Coin.model_validate(c) for c in json.loads(cached_data_after_update)]

        logger.error("Не удалось получить список монет даже после попытки обновления.")
        return []

# ---

# bot/services/price_service.py
# Сервис также обновлён для использования общих зависимостей.

import logging
from typing import Dict, List, Optional

from redis.asyncio import Redis
import aiohttp

from bot.config.settings import PriceServiceConfig, EndpointsConfig
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
        config: PriceServiceConfig,
        endpoints: EndpointsConfig,
    ):
        self.redis = redis
        self.http_session = http_session
        self.coin_list_service = coin_list_service
        self.config = config
        self.endpoints = endpoints
        self._price_url = str(endpoints.coingecko_api_simple_price)

    def _get_cache_key(self, coin_id: str) -> str:
        """Генерирует консистентный ключ для кэша цены монеты."""
        return f"cache:price:{coin_id}"

    async def get_prices(self, coin_ids: List[str], vs_currency: str = 'usd') -> Dict[str, Optional[float]]:
        """
        Получает цены для списка ID монет. Сначала проверяет кэш,
        затем запрашивает недостающие цены у API.
        """
        prices: Dict[str, Optional[float]] = {}
        coins_to_fetch: List[str] = []

        for coin_id in coin_ids:
            cached_price = await self.redis.get(self._get_cache_key(coin_id))
            if cached_price:
                prices[coin_id] = float(cached_price)
            else:
                coins_to_fetch.append(coin_id)

        if not coins_to_fetch:
            return prices

        logger.info(f"Запрос цен с API для: {coins_to_fetch}")
        params = {
            'ids': ','.join(coins_to_fetch),
            'vs_currencies': vs_currency
        }
        try:
            async with self.http_session.get(self._price_url, params=params) as response:
                response.raise_for_status()
                api_data = await response.json()

                for coin_id, price_data in api_data.items():
                    price = price_data.get(vs_currency)
                    if price is not None:
                        prices[coin_id] = float(price)
                        await self.redis.set(
                            self._get_cache_key(coin_id),
                            price,
                            ex=self.config.cache_ttl_seconds
                        )
                    else:
                        prices[coin_id] = None
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при получении цен: {e}")
            for coin_id in coins_to_fetch:
                prices[coin_id] = None  # Помечаем как неудавшиеся

        return prices
