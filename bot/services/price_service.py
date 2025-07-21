import logging
import json
from typing import Optional, Dict

import aiohttp
import redis.asyncio as redis

from bot.config.settings import settings
from bot.utils.models import CryptoCoin
from bot.services.coin_list_service import CoinListService
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class PriceService:
    """
    "Альфа" сервис для получения цен на криптовалюты с трехуровневой системой
    источников (CoinGecko, CoinPaprika, CoinMarketCap) и интеллектуальным
    кешированием в Redis.
    """
    def __init__(
        self, 
        coin_list_service: CoinListService, 
        redis_client: redis.Redis, 
        http_session: aiohttp.ClientSession
    ):
        """
        Инициализирует сервис с необходимыми зависимостями.
        """
        self.coin_list_service = coin_list_service
        self.redis = redis_client
        self.session = http_session
        self.cache_ttl_seconds = 120  # Кешируем успешные ответы на 2 минуты
        self.not_found_cache_ttl_seconds = 300 # Кешируем "не найдено" на 5 минут

    async def _fetch_from_coingecko(self, query_norm: str, coin_list_dict: Dict) -> Optional[CryptoCoin]:
        """Приватный метод для получения данных с CoinGecko."""
        # ... (этот код остается без изменений) ...
        pass

    async def _fetch_from_coinpaprika(self, query_norm: str, coin_list_dict: Dict) -> Optional[CryptoCoin]:
        """Приватный метод для получения данных с CoinPaprika."""
        # ... (этот код остается без изменений) ...
        pass

    # --- НОВЫЙ МЕТОД ДЛЯ COINMARKETCAP ---
    async def _fetch_from_cmc(self, query_norm: str, coin_list_dict: Dict) -> Optional[CryptoCoin]:
        """Приватный метод для получения данных с CoinMarketCap."""
        if not settings.cmc_api_key:
            logger.warning("CMC API ключ не предоставлен, пропуск запроса.")
            return None
        
        try:
            symbol = query_norm.upper()
            url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
            headers = {'X-CMC_PRO_API_KEY': settings.cmc_api_key}
            params = {'symbol': symbol}
            
            cmc_data = await make_request(self.session, url, headers=headers, params=params)

            if not (cmc_data and cmc_data.get('data') and cmc_data['data'].get(symbol)):
                return None

            coin_data = cmc_data['data'][symbol][0] # CMC возвращает список, берем первый
            quote = coin_data.get('quote', {}).get('USD', {})

            if not quote:
                return None

            # Адаптируем данные от CMC к нашей модели CryptoCoin
            mapped_data = {
                'name': coin_data.get('name'),
                'symbol': coin_data.get('symbol'),
                'price': quote.get('price'),
                'price_change_24h': quote.get('percent_change_24h'),
                'algorithm': coin_list_dict.get(symbol) # Алгоритм берем из наших данных
            }
            
            logger.info(f"Успешно получена цена для '{query_norm}' с CoinMarketCap.")
            return CryptoCoin.model_validate(mapped_data)

        except Exception as e:
            logger.error(f"Ошибка при запросе к CoinMarketCap для {query_norm}: {e}")
            return None

    async def get_crypto_price(self, query: str) -> Optional[CryptoCoin]:
        """
        Получает цену криптовалюты, используя кеш в Redis и несколько источников.
        """
        query_norm = settings.ticker_aliases.get(query.strip().lower(), query.strip().lower())
        cache_key = f"price_cache:{query_norm}"

        # 1. Проверяем кеш в Redis
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            cached_str = cached_data.decode('utf-8')
            if cached_str == "NOT_FOUND":
                logger.info(f"'{query_norm}' закеширован как 'не найдено'.")
                return None
            logger.info(f"Возвращена закешированная цена для '{query_norm}'.")
            return CryptoCoin.model_validate_json(cached_str)

        # 2. Если в кеше нет, идем в API
        coin_list_dict = await self.coin_list_service.get_coin_list()
        
        # Попытка №1: CoinGecko
        coin = await self._fetch_from_coingecko(query_norm, coin_list_dict)
        
        # Попытка №2: CoinPaprika, если первая не удалась
        if not coin:
            logger.warning(f"Не удалось получить цену с CoinGecko для '{query_norm}'. Переключаюсь на CoinPaprika.")
            coin = await self._fetch_from_coinpaprika(query_norm, coin_list_dict)

        # --- НОВЫЙ ШАГ: Попытка №3: CoinMarketCap, если и вторая не удалась ---
        if not coin:
            logger.warning(f"Не удалось получить цену с CoinPaprika для '{query_norm}'. Переключаюсь на CoinMarketCap.")
            coin = await self._fetch_from_cmc(query_norm, coin_list_dict)

        # 3. Сохраняем результат в кеш
        if coin:
            await self.redis.set(cache_key, coin.model_dump_json(), ex=self.cache_ttl_seconds)
        else:
            logger.error(f"Не удалось получить цену для '{query_norm}' со всех источников. Кеширую как 'не найдено'.")
            await self.redis.set(cache_key, "NOT_FOUND", ex=self.not_found_cache_ttl_seconds)
            
        return coin
