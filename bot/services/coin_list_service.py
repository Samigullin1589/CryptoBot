import logging
import aiohttp
from typing import List, Optional
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.models import CryptoCoin
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    @alru_cache(maxsize=1)
    async def get_coin_list(self) -> List[CryptoCoin]:
        """Получает полный список монет с их ID для использования в других API."""
        logger.info("Обновление списка монет...")
        async with aiohttp.ClientSession() as session:
            # Пытаемся получить список с CoinGecko
            cg_data = await make_request(session, f"{settings.coingecko_api_base}/coins/list?include_platform=true")
            if isinstance(cg_data, list):
                logger.info(f"Успешно получено {len(cg_data)} монет с CoinGecko.")
                return [CryptoCoin(**item) for item in cg_data]

            # Если CoinGecko не удался, пробуем MinerStat
            ms_data = await make_request(session, f"{settings.minerstat_api_base}/coins")
            if isinstance(ms_data, list):
                logger.warning("CoinGecko не ответил, используется резервный список с MinerStat.")
                logger.info(f"Успешно получено {len(ms_data)} монет с MinerStat.")
                # Адаптируем ответ MinerStat под нашу модель
                return [CryptoCoin(id=item.get('id', item['coin'].lower()), symbol=item['coin'], name=item['name']) for item in ms_data]

        logger.error("Не удалось получить список монет ни из одного источника.")
        return []

    async def get_coin_id(self, ticker: str) -> Optional[str]:
        """Находит ID монеты (для CoinGecko) по ее тикеру."""
        coins = await self.get_coin_list()
        ticker_lower = ticker.lower()
        for coin in coins:
            if coin.symbol.lower() == ticker_lower:
                return coin.id
        return None