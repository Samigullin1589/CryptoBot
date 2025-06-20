# bot/services/price_service.py
import asyncio
import logging
from typing import Optional

import aiohttp
from async_cache import cached
from cachetools import TTLCache # или LRUCache

from bot.config.settings import settings
from bot.utils.models import CryptoCoin
from bot.utils.helpers import make_request
from bot.services.coin_list_service import CoinListService

logger = logging.getLogger(__name__)

class PriceService:
    # Кэш, как атрибут класса
    cache = TTLCache(maxsize=100, ttl=300)

    def __init__(self, coin_list_service: CoinListService):
        self.coin_list_service = coin_list_service

    @cached(cache)
    async def get_crypto_price(self, query: str) -> Optional[CryptoCoin]:
        """
        Получает цену криптовалюты, используя несколько источников данных.
        """
        query_norm = settings.ticker_aliases.get(query.strip().lower(), query.strip().lower())
        
        async with aiohttp.ClientSession() as session:
            # --- Попытка 1: CoinGecko (основной источник) ---
            logger.info(f"Attempting to fetch price for '{query_norm}' from CoinGecko.")
            cg_search_data = await make_request(session, f"{settings.coingecko_api_base}/search?query={query_norm}")
            
            if cg_search_data is None: 
                 await asyncio.sleep(2)

            if cg_search_data and cg_search_data.get('coins'):
                coin_id = cg_search_data['coins'][0].get('id')
                market_data_list = await make_request(session, f"{settings.coingecko_api_base}/coins/markets?vs_currency=usd&ids={coin_id}")
                if market_data_list:
                    md = market_data_list[0]
                    symbol = md.get('symbol', '').upper()
                    coin_list = await self.coin_list_service.get_coin_list()
                    logger.info(f"Successfully fetched price for '{query_norm}' from CoinGecko.")
                    return CryptoCoin(
                        id=md.get('id'), symbol=symbol, name=md.get('name'), price=md.get('current_price', 0.0),
                        price_change_24h=md.get('price_change_percentage_24h'), algorithm=coin_list.get(symbol)
                    )
            
            # --- Попытка 2: CoinPaprika (резервный источник) ---
            logger.warning(f"Failed to get price from CoinGecko for '{query_norm}'. Falling back to CoinPaprika.")
            cp_search_data = await make_request(session, f"{settings.coinpaprika_api_base}/search?q={query_norm}&c=currencies")
            if cp_search_data and cp_search_data.get('currencies'):
                target_coin = next((c for c in cp_search_data['currencies'] if c['symbol'].lower() == query_norm), cp_search_data['currencies'][0])
                coin_id = target_coin.get('id')
                
                ticker_data = await make_request(session, f"{settings.coinpaprika_api_base}/tickers/{coin_id}")
                if ticker_data:
                    quotes = ticker_data.get('quotes', {}).get('USD', {})
                    symbol = ticker_data.get('symbol', '').upper()
                    coin_list = await self.coin_list_service.get_coin_list()
                    logger.info(f"Successfully fetched price for '{query_norm}' from CoinPaprika.")
                    return CryptoCoin(
                        id=ticker_data.get('id'), symbol=symbol, name=ticker_data.get('name'),
                        price=quotes.get('price', 0.0), price_change_24h=quotes.get('percent_change_24h'),
                        algorithm=coin_list.get(symbol)
                    )

        logger.error(f"Failed to get price for '{query_norm}' from all sources.")
        return None
