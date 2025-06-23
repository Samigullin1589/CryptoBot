import logging
from typing import Optional

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.models import CryptoCoin
from bot.services.coin_list_service import CoinListService
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self, coin_list_service: CoinListService):
        self.coin_list_service = coin_list_service

    @alru_cache(maxsize=100, ttl=300)
    async def get_crypto_price(self, query: str) -> Optional[CryptoCoin]:
        query_norm = settings.ticker_aliases.get(query.strip().lower(), query.strip().lower())
        
        async with aiohttp.ClientSession() as session:
            # Попытка №1: CoinGecko
            logger.info(f"Attempting to fetch price for '{query_norm}' from CoinGecko.")
            cg_search_data = await make_request(session, f"{settings.coingecko_api_base}/search?query={query_norm}")
            
            if cg_search_data and cg_search_data.get('coins'):
                if cg_search_data['coins']:
                    coin_id = cg_search_data['coins'][0].get('id')
                    if coin_id:
                        market_data_list = await make_request(session, f"{settings.coingecko_api_base}/coins/markets?vs_currency=usd&ids={coin_id}")
                        if market_data_list and isinstance(market_data_list, list) and market_data_list:
                            md = market_data_list[0]
                            symbol = md.get('symbol', '').upper()
                            coin_list_dict = await self.coin_list_service.get_coin_list()
                            logger.info(f"Successfully fetched price for '{query_norm}' from CoinGecko.")
                            return CryptoCoin.model_validate(md, context={"algorithm_map": coin_list_dict})

            # Попытка №2: CoinPaprika
            logger.warning(f"Failed to get price from CoinGecko for '{query_norm}'. Falling back to CoinPaprika.")
            cp_search_data = await make_request(session, f"{settings.coinpaprika_api_base}/search?q={query_norm}&c=currencies")
            if cp_search_data and cp_search_data.get('currencies'):
                if cp_search_data['currencies']:
                    target_coin = next((c for c in cp_search_data['currencies'] if c['symbol'].lower() == query_norm), cp_search_data['currencies'][0])
                    coin_id = target_coin.get('id')
                    if coin_id:
                        ticker_data = await make_request(session, f"{settings.coinpaprika_api_base}/tickers/{coin_id}")
                        if ticker_data:
                            quotes = ticker_data.get('quotes', {}).get('USD', {})
                            symbol = ticker_data.get('symbol', '').upper()
                            coin_list_dict = await self.coin_list_service.get_coin_list()
                            logger.info(f"Successfully fetched price for '{query_norm}' from CoinPaprika.")
                            
                            # Собираем данные в один словарь для валидации
                            combined_data = {
                                **ticker_data, 
                                **quotes,
                                'price_change_24h': quotes.get('percent_change_24h')
                            }
                            return CryptoCoin.model_validate(combined_data, context={"algorithm_map": coin_list_dict})

        logger.error(f"Failed to get price for '{query_norm}' from all sources.")
        return None