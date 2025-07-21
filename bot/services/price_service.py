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
    "Альфа" сервис для получения цен на криптовалюты с интеллектуальным
    кешированием в Redis для предотвращения rate-limit'ов и ускорения ответов.
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
        try:
            search_url = f"{settings.coingecko_api_base}/search?query={query_norm}"
            cg_search_data = await make_request(self.session, search_url)
            
            if not (cg_search_data and cg_search_data.get('coins')):
                return None
            
            coin_id = cg_search_data['coins'][0].get('id')
            if not coin_id:
                return None

            market_url = f"{settings.coingecko_api_base}/coins/markets?vs_currency=usd&ids={coin_id}"
            market_data_list = await make_request(self.session, market_url)

            if not (market_data_list and isinstance(market_data_list, list)):
                return None
            
            md = market_data_list[0]
            symbol = md.get('symbol', '').upper()
            md['algorithm'] = coin_list_dict.get(symbol)
            logger.info(f"Успешно получена цена для '{query_norm}' с CoinGecko.")
            return CryptoCoin.model_validate(md)
            
        except Exception as e:
            logger.error(f"Ошибка при запросе к CoinGecko для {query_norm}: {e}")
            return None

    async def _fetch_from_coinpaprika(self, query_norm: str, coin_list_dict: Dict) -> Optional[CryptoCoin]:
        """Приватный метод для получения данных с CoinPaprika."""
        try:
            search_url = f"{settings.coinpaprika_api_base}/search?q={query_norm}&c=currencies"
            cp_search_data = await make_request(self.session, search_url)

            if not (cp_search_data and cp_search_data.get('currencies')):
                return None

            target_coin = next((c for c in cp_search_data['currencies'] if c['symbol'].lower() == query_norm), cp_search_data['currencies'][0])
            coin_id = target_coin.get('id')
            if not coin_id:
                return None

            ticker_url = f"{settings.coinpaprika_api_base}/tickers/{coin_id}"
            ticker_data = await make_request(self.session, ticker_url)

            if not ticker_data:
                return None
                
            quotes = ticker_data.get('quotes', {}).get('USD', {})
            symbol = ticker_data.get('symbol', '').upper()
            combined_data = {**ticker_data, **quotes, 'algorithm': coin_list_dict.get(symbol)}
            logger.info(f"Успешно получена цена для '{query_norm}' с CoinPaprika.")
            return CryptoCoin.model_validate(combined_data)

        except Exception as e:
            logger.error(f"Ошибка при запросе к CoinPaprika для {query_norm}: {e}")
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

        # 3. Сохраняем результат в кеш
        if coin:
            await self.redis.set(cache_key, coin.model_dump_json(), ex=self.cache_ttl_seconds)
        else:
            logger.error(f"Не удалось получить цену для '{query_norm}' со всех источников. Кеширую как 'не найдено'.")
            await self.redis.set(cache_key, "NOT_FOUND", ex=self.not_found_cache_ttl_seconds)
            
        return coin
