import logging
from typing import Dict

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    @alru_cache(maxsize=1, ttl=21600)  # Кэшируем на 6 часов
    async def get_coin_list(self) -> Dict[str, str]:
        """
        Получает и кэширует список монет с их алгоритмами в виде словаря {СИМВОЛ: АЛГОРИТМ}.
        Приоритет у MinerStat, так как там есть алгоритмы.
        """
        logger.info("Updating coin list with algorithms...")
        async with aiohttp.ClientSession() as session:
            # Источник №1: MinerStat (дает алгоритмы)
            minerstat_data = await make_request(session, f"{settings.minerstat_api_base}/coins")
            if minerstat_data and isinstance(minerstat_data, list):
                logger.info(f"Successfully fetched {len(minerstat_data)} coins from MinerStat.")
                return {coin['coin']: coin['algorithm'] for coin in minerstat_data if 'coin' in coin and 'algorithm' in coin}

            # Резервный источник №2: CoinGecko (не дает алгоритмы, но лучше чем ничего)
            logger.warning("MinerStat failed, using CoinGecko as a fallback.")
            gecko_data = await make_request(session, f"{settings.coingecko_api_base}/coins/list")
            if gecko_data and isinstance(gecko_data, list):
                logger.info(f"Successfully fetched {len(gecko_data)} coins from CoinGecko.")
                return {coin['symbol'].upper(): "Unknown" for coin in gecko_data if 'symbol' in coin}
        
        logger.error("Failed to fetch coin list from all sources.")
        return {}