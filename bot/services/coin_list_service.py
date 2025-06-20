# bot/services/coin_list_service.py
import logging
from typing import Dict

import aiohttp
from cachetools import cached, LRUCache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    # Кэш, как атрибут класса
    cache = LRUCache(maxsize=1)

    @cached(cache)
    async def get_coin_list(self) -> Dict[str, str]:
        """
        Загружает и возвращает словарь, где ключ - тикер монеты, 
        а значение - ее алгоритм.
        """
        logger.info("Updating coin list cache from Minerstat...")
        coin_algo_map = {}
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, f"{settings.minerstat_api_base}/coins")
            if data:
                for coin_data in data:
                    if symbol := coin_data.get('coin'):
                        coin_algo_map[symbol.upper()] = coin_data.get('algorithm')
        
        if coin_algo_map:
            logger.info(f"Coin list cache updated with {len(coin_algo_map)} coins.")
        else:
            logger.warning("Failed to update coin list cache. Data was empty.")

        return coin_algo_map
