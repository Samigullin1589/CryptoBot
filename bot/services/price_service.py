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
    источников (CoinGecko, CoinPaprika, CryptoCompare) и интеллектуальным
    кешированием в Redis.
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
        self.cache_ttl_seconds = 120
        self.not_found_cache_ttl_seconds = 300

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

    # --- ЗАМЕНА: Вместо CMC теперь CryptoCompare ---
    async def _fetch_from_cryptocompare(self, query_norm: str, coin_list_dict: Dict) -> Optional[CryptoCoin]:
        """Приватный метод для получения данных с CryptoCompare."""
        if not settings.cryptocompare_api_key:
            logger.warning("CryptoCompare API ключ не предоставлен, пропуск запроса.")
            return None
        
        try:
            symbol = query_norm.upper()
            url = f"{settings.cryptocompare_api_base}/data/pricemultifull"
            params = {
                'fsyms': symbol,
                'tsyms': 'USD',
                'api_key': settings.cryptocompare_api_key
            }
            
            cc_data = await make_request(self.session, url, params=params)

            if not (cc_data and 'RAW' in cc_data and symbol in cc_data['RAW'] and 'USD' in cc_data['RAW'][symbol]):
                return None

            coin_data = cc_data['RAW'][symbol]['USD']
            coin_info_dict = coin_list_dict.get(symbol, {})

            # Адаптируем данные от CryptoCompare к нашей модели CryptoCoin
            mapped_data = {
                'name': coin_info_dict.get('name', symbol), # Имя берем из наших данных, если есть
                'symbol': symbol,
                'price': coin_data.get('PRICE'),
                'price_change_24h': coin_data.get('CHANGEPCT24HOUR'),
                'algorithm': coin_info_dict.get('algorithm')
            }
            
            logger.info(f"Успешно получена цена для '{query_norm}' с CryptoCompare.")
            return CryptoCoin.model_validate(mapped_data)

        except Exception as e:
            logger.error(f"Ошибка при запросе к CryptoCompare для {query_norm}: {e}")
            return None

    async def get_crypto_price(self, query: str) -> Optional[CryptoCoin]:
        """
        Получает цену криптовалюты, используя кеш в Redis и несколько источников.
        """
        query_norm = settings.ticker_aliases.get(query.strip().lower(), query.strip().lower())
        cache_key = f"price_cache:{query_norm}"

        cached_data = await self.redis.get(cache_key)
        if cached_data:
            cached_str = cached_data.decode('utf-8')
            if cached_str == "NOT_FOUND":
                return None
            return CryptoCoin.model_validate_json(cached_str)

        coin_list_dict = await self.coin_list_service.get_coin_list()
        
        coin = await self._fetch_from_coingecko(query_norm, coin_list_dict)
        
        if not coin:
            logger.warning(f"Не удалось получить цену с CoinGecko для '{query_norm}'. Переключаюсь на CoinPaprika.")
            coin = await self._fetch_from_coinpaprika(query_norm, coin_list_dict)

        # --- ЗАМЕНА: Вместо CMC теперь CryptoCompare ---
        if not coin:
            logger.warning(f"Не удалось получить цену с CoinPaprika для '{query_norm}'. Переключаюсь на CryptoCompare.")
            coin = await self._fetch_from_cryptocompare(query_norm, coin_list_dict)

        if coin:
            await self.redis.set(cache_key, coin.model_dump_json(), ex=self.cache_ttl_seconds)
        else:
            logger.error(f"Не удалось получить цену для '{query_norm}' со всех источников. Кеширую как 'не найдено'.")
            await self.redis.set(cache_key, "NOT_FOUND", ex=self.not_found_cache_ttl_seconds)
            
        return coin
