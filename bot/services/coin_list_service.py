# bot/services/coin_list_service.py
import logging
from typing import Dict

import aiohttp
# Как и рекомендовано в аудите, используем LRUCache для этих данных
from cachetools import cached, LRUCache

# Импорты для новой структуры
from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    def __init__(self):
        """
        Сервис для получения и кэширования списка всех монет и их алгоритмов.
        """
        # Используем LRUCache, так как список монет меняется редко,
        # а некоторые монеты запрашиваются чаще других.
        self.cache = LRUCache(maxsize=1) # Кэшируем только один большой объект - сам список

    # Используем lambda, чтобы декоратор @cached мог получить доступ к self.cache
    @cached(cache=lambda self: self.cache)
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
        
        # Проверяем, что данные успешно загружены, прежде чем обновлять кэш
        if coin_algo_map:
            logger.info(f"Coin list cache updated with {len(coin_algo_map)} coins.")
        else:
            logger.warning("Failed to update coin list cache. Data was empty.")

        return coin_algo_map
