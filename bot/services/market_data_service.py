import logging
import aiohttp
from typing import Optional, Dict

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class MarketDataService:
    async def get_fear_and_greed_index(self) -> Optional[Dict]:
        """Получает индекс страха и жадности с Alternative.me."""
        logger.info("Запрос индекса страха и жадности...")
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, settings.fear_and_greed_api_url)
            if isinstance(data, dict) and "data" in data and data["data"]:
                logger.info("Индекс страха и жадности успешно получен.")
                return data["data"][0]
        logger.error("Не удалось получить индекс страха и жадности.")
        return None

    async def get_usd_rub_rate(self) -> Optional[float]:
        """Получает курс доллара к рублю с API ЦБ РФ."""
        logger.info("Запрос курса USD/RUB...")
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, settings.cbr_daily_json_url)
            if isinstance(data, dict) and "Valute" in data and "USD" in data["Valute"]:
                rate = data["Valute"]["USD"]["Value"]
                logger.info(f"Курс USD/RUB успешно получен: {rate}")
                return rate
        logger.error("Не удалось получить курс USD/RUB.")
        return None