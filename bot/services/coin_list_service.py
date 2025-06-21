import logging
from typing import Dict

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    @alru_cache(maxsize=1, ttl=21600)  # Используем новый декоратор async-lru с кэшем на 6 часов
    async def get_coin_list(self) -> Dict[str, str]:
        """Получает и кэширует список монет и их алгоритмов с MinerStat."""
        logger.info("Updating coin list with algorithms from MinerStat...")
        async with aiohttp.ClientSession() as session:
            # Используем URL из настроек
            data = await make_request(session, f"{settings.minerstat_api_base}/coins")
            if data and isinstance(data, list):
                logger.info(f"Successfully fetched {len(data)} coins from MinerStat.")
                # Создаем словарь {ТИКЕР: АЛГОРИТМ}
                return {
                    coin['coin']: coin['algorithm']
                    for coin in data if 'coin' in coin and 'algorithm' in coin
                }
        logger.warning("Failed to fetch coin list from MinerStat. Returning empty dict.")
        return {}