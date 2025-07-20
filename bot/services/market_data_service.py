import asyncio
import logging
from typing import Optional

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

# --- НОВЫЙ РЕЗЕРВНЫЙ URL ---
BLOCKCHAIN_INFO_BLOCK_COUNT_URL = "https://blockchain.info/q/getblockcount"

class MarketDataService:
    @alru_cache(maxsize=1, ttl=14400)
    async def get_fear_and_greed_index(self) -> Optional[dict]:
        """Получает Индекс Страха и Жадности, используя несколько источников."""
        logger.info("Fetching Fear & Greed Index...")
        async with aiohttp.ClientSession() as session:
            # Пробуем получить с CoinMarketCap, если есть ключ
            if settings.cmc_api_key:
                headers = {'X-CMC_PRO_API_KEY': settings.cmc_api_key}
                data = await make_request(session, settings.cmc_fear_and_greed_url, headers=headers)
                if data and 'data' in data and data['data']:
                    fng_data = data['data'][0] # CMC returns a list
                    logger.info("Fetched F&G index from CoinMarketCap")
                    return {
                        'value': fng_data['score'],
                        'value_classification': fng_data['rating']
                    }
                logger.warning("Failed to fetch from CMC, falling back to Alternative.me")
            
            # Резервный источник
            data = await make_request(session, settings.fear_and_greed_api_url)
            if data and 'data' in data and data['data']:
                logger.info("Fetched F&G index from Alternative.me")
                return data['data'][0]
        
        logger.error("Failed to fetch F&G index from all sources.")
        return None

    @alru_cache(maxsize=1, ttl=43200)
    async def get_usd_rub_rate(self) -> float:
        """Получает курс USD/RUB от Центробанка РФ."""
        logger.info("Fetching USD/RUB exchange rate.")
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, settings.cbr_daily_json_url)
            if data and "Valute" in data and "USD" in data["Valute"]:
                rate = data["Valute"]["USD"]["Value"]
                logger.info(f"Current USD/RUB rate: {rate}")
                return float(rate)
        logger.warning("Could not fetch USD/RUB rate. Using fallback rate 90.0.")
        return 90.0

    async def get_halving_info(self) -> str:
        """
        Получает информацию о халвинге Bitcoin с использованием основного и резервного источников.
        """
        logger.info("Fetching Bitcoin halving info...")
        current_block = None
        
        async with aiohttp.ClientSession() as session:
            # 1. Основной источник: mempool.space
            logger.info("Trying primary source for block height: mempool.space")
            height_str = await make_request(session, settings.btc_halving_url, response_type='text', timeout=5)
            if height_str and height_str.isdigit():
                current_block = int(height_str)
                logger.info(f"Fetched block height from mempool.space: {current_block}")
            else:
                logger.warning("Primary source failed. Trying fallback source: blockchain.info")
                # 2. Резервный источник: blockchain.info
                height_str_fallback = await make_request(session, BLOCKCHAIN_INFO_BLOCK_COUNT_URL, response_type='text', timeout=10)
                if height_str_fallback and height_str_fallback.isdigit():
                    current_block = int(height_str_fallback)
                    logger.info(f"Fetched block height from blockchain.info: {current_block}")

        if current_block is None:
            logger.error("Failed to fetch block height from all sources.")
            return "❌ Не удалось получить данные о халвинге. Внешние сервисы временно недоступны."
        
        halving_interval = 210000
        blocks_left = halving_interval - (current_block % halving_interval)
        days_left = blocks_left / 144
        
        return (f"⏳ <b>До халвинга Bitcoin осталось:</b>\n\n"
                f"🧱 <b>Блоков:</b> <code>{blocks_left:,}</code>\n"
                f"🗓 <b>Примерно дней:</b> <code>{days_left:.1f}</code>")

    async def get_btc_network_status(self) -> str:
        """
        Получает статус сети Bitcoin (комиссии и мемпул) с обработкой ошибок.
        """
        logger.info("Fetching Bitcoin network status...")
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [
                    make_request(session, settings.btc_fees_url, timeout=10),
                    make_request(session, settings.btc_mempool_url, timeout=10)
                ]
                results = await asyncio.gather(*tasks)
                fees_data, mempool_data = results

            if not fees_data or not mempool_data:
                logger.error("Failed to fetch BTC network status, one of the sources returned empty data.")
                return "❌ Не удалось получить статус сети BTC. Внешний сервис вернул неполные данные."
            
            return (f"📡 <b>Статус сети Bitcoin:</b>\n\n"
                    f"📈 <b>Транзакций в мемпуле:</b> <code>{mempool_data.get('count', 'N/A'):,}</code>\n\n"
                    f"💸 <b>Рекомендуемые комиссии (sat/vB):</b>\n"
                    f"  - 🚀 Высокий: <code>{fees_data.get('fastestFee', 'N/A')}</code>\n"
                    f"  - 🚶‍♂️ Средний: <code>{fees_data.get('halfHourFee', 'N/A')}</code>\n"
                    f"  - 🐢 Низкий: <code>{fees_data.get('hourFee', 'N/A')}</code>")
        
        except asyncio.TimeoutError:
            logger.error("TimeoutError while fetching BTC network status from mempool.space.")
            return "❌ Не удалось получить статус сети BTC. Внешний сервис (mempool.space) не отвечает."
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching BTC network status: {e}")
            return "❌ Произошла непредвиденная ошибка при получении статуса сети BTC."
