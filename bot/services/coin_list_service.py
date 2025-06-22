import logging
from typing import Dict, Optional

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    @alru_cache(maxsize=1, ttl=21600)  # Кэшируем на 6 часов
    async def get_coin_list(self) -> Dict[str, str]:
        """
        Получает и кэширует список монет и их алгоритмов, возвращая словарь.
        """
        logger.info("Updating coin list with algorithms...")
        async with aiohttp.ClientSession() as session:
            # Сначала пытаемся получить с CoinGecko
            gecko_data = await make_request(session, f"{settings.coingecko_api_base}/coins/list?include_platform=true")
            if gecko_data and isinstance(gecko_data, list):
                logger.info(f"Successfully fetched {len(gecko_data)} coins from CoinGecko.")
                # Преобразуем список словарей в словарь {символ: id}
                # Это не дает алгоритмы, но дает нам ID для других запросов
                return {coin['symbol'].upper(): coin['id'] for coin in gecko_data if 'symbol' in coin and 'id' in coin}

            # Если CoinGecko не ответил, используем MinerStat
            logger.warning("CoinGecko failed, using MinerStat as a fallback.")
            minerstat_data = await make_request(session, f"{settings.minerstat_api_base}/coins")
            if minerstat_data and isinstance(minerstat_data, list):
                logger.info(f"Successfully fetched {len(minerstat_data)} coins from MinerStat.")
                # Этот источник дает нам алгоритмы
                return {coin['coin']: coin['algorithm'] for coin in minerstat_data if 'coin' in coin and 'algorithm' in coin}
        
        logger.error("Failed to fetch coin list from all sources.")
        return {}