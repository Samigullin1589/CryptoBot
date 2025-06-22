import logging
import aiohttp
from typing import Optional

from bot.config.settings import settings
from bot.services.coin_list_service import CoinListService
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self, coin_list_service: CoinListService):
        self.coin_list_service = coin_list_service

    async def get_price(self, ticker: str) -> Optional[float]:
        """
        Получает цену для указанного тикера, используя несколько источников.
        """
        logger.info(f"Попытка получить цену для '{ticker}'...")

        # Сначала пытаемся получить цену через CoinGecko, так как он самый точный
        price = await self._get_price_from_coingecko(ticker)
        if price is not None:
            logger.info(f"Цена для '{ticker}' успешно получена с CoinGecko: {price}")
            return price

        # Если CoinGecko не сработал, пробуем CoinPaprika
        logger.warning(f"Не удалось получить цену для '{ticker}' с CoinGecko. Пробуем CoinPaprika.")
        price = await self._get_price_from_coinpaprika(ticker)
        if price is not None:
            logger.info(f"Цена для '{ticker}' успешно получена с CoinPaprika: {price}")
            return price

        logger.error(f"Не удалось получить цену для '{ticker}' ни из одного источника.")
        return None

    async def _get_price_from_coingecko(self, ticker: str) -> Optional[float]:
        coin_id = await self.coin_list_service.get_coin_id(ticker)
        if not coin_id:
            logger.warning(f"Не найден ID для тикера '{ticker}' в CoinGecko.")
            return None

        url = f"{settings.coingecko_api_base}/simple/price?ids={coin_id}&vs_currencies=usd"
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, url)
            if isinstance(data, dict) and coin_id in data and "usd" in data[coin_id]:
                return data[coin_id]["usd"]
        return None

    async def _get_price_from_coinpaprika(self, ticker: str) -> Optional[float]:
        # CoinPaprika часто использует формат "btc-bitcoin"
        coin_id = await self.coin_list_service.get_coin_id(ticker)
        if not coin_id:
            return None # Уже залогировали в coingecko

        ticker_lower = ticker.lower()
        coinpaprika_id = f"{ticker_lower}-{coin_id.replace(ticker_lower, '').strip('-')}" if coin_id != ticker_lower else ticker_lower

        url = f"{settings.coinpaprika_api_base}/tickers/{coinpaprika_id}"
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, url)
            if isinstance(data, dict) and "quotes" in data and "USD" in data["quotes"] and "price" in data["quotes"]["USD"]:
                return data["quotes"]["USD"]["price"]
        return None