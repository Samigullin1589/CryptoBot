import logging
from typing import Dict

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    @alru_cache(maxsize=1, ttl=21600)
    async def get_coin_list(self) -> Dict[str, str]:
        """
        Получает и кэширует список монет с их алгоритмами в виде словаря {СИМВОЛ: АЛГОРИТМ}.
        """
        logger.info("Updating coin list with algorithms...")
        async with aiohttp.ClientSession() as session:
            # Используем MinerStat как основной источник, так как он дает алгоритмы
            minerstat_data = await make_request(session, f"{settings.minerstat_api_base}/coins")
            if minerstat_data and isinstance(minerstat_data, list):
                logger.info(f"Successfully fetched {len(minerstat_data)} coins from MinerStat.")
                return {coin['coin']: coin['algorithm'] for coin in minerstat_data if 'coin' in coin and 'algorithm' in coin}
        
        logger.error("Failed to fetch coin list from MinerStat.")
        return {}