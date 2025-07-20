import asyncio
import logging
from typing import Optional

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

# --- НОВЫЕ, БЫСТРЫЕ И НАДЕЖНЫЕ ИСТОЧНИКИ ДАННЫХ ---
BLOCKCHAIN_INFO_BLOCK_COUNT_URL = "https://blockchain.info/q/getblockcount"
BLOCKCHAIR_BTC_STATS_URL = "https://api.blockchair.com/bitcoin/stats"

class MarketDataService:
    @alru_cache(maxsize=1, ttl=14400)
    async def get_fear_and_greed_index(self) -> Optional[dict]:
        """Получает Индекс Страха и Жадности, используя несколько источников."""
        logger.info("Fetching Fear & Greed Index...")
        async with aiohttp.ClientSession() as session:
            if settings.cmc_api_key:
                headers = {'X-CMC_PRO_API_KEY': settings.cmc_api_key}
                data = await make_request(session, settings.cmc_fear_and_greed_url, headers=headers)
                if data and 'data' in data and data['data']:
                    fng_data = data['data'][0]
                    logger.info("Fetched F&G index from CoinMarketCap")
                    return {'value': fng_data['score'], 'value_classification': fng_data['rating']}
                logger.warning("Failed to fetch from CMC, falling back to Alternative.me")
            
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
        Получает информацию о халвинге Bitcoin, используя быстрый и надежный источник.
        """
        logger.info("Fetching Bitcoin halving info from blockchain.info...")
        current_block = None
        
        async with aiohttp.ClientSession() as session:
            # Используем blockchain.info как единственный, надежный источник
            height_str = await make_request(session, BLOCKCHAIN_INFO_BLOCK_COUNT_URL, response_type='text', timeout=7)
            if height_str and height_str.isdigit():
                current_block = int(height_str)
                logger.info(f"Fetched block height from blockchain.info: {current_block}")

        if current_block is None:
            logger.error("Failed to fetch block height from blockchain.info.")
            return "❌ Не удалось получить данные о халвинге. Внешний сервис временно недоступен."
        
        halving_interval = 210000
        blocks_left = halving_interval - (current_block % halving_interval)
        days_left = blocks_left / 144
        
        return (f"⏳ <b>До халвинга Bitcoin осталось:</b>\n\n"
                f"🧱 <b>Блоков:</b> <code>{blocks_left:,}</code>\n"
                f"🗓 <b>Примерно дней:</b> <code>{days_left:.1f}</code>")

    async def get_btc_network_status(self) -> str:
        """
        Получает статус сети Bitcoin, используя быстрый и надежный источник.
        """
        logger.info("Fetching Bitcoin network status from blockchair.com...")
        try:
            async with aiohttp.ClientSession() as session:
                data = await make_request(session, BLOCKCHAIR_BTC_STATS_URL, timeout=7)

            if not data or "data" not in data:
                logger.error("Failed to fetch BTC network status from blockchair.com, response has invalid structure.")
                return "❌ Не удалось получить статус сети BTC. Внешний сервис вернул неверные данные."
            
            stats = data["data"]
            # Blockchair дает комиссию в satoshi per byte, что и нужно (sat/vB)
            # Умножаем на 1024 для примерного перевода в vB, если API дает sat/kB
            # Но blockchair обычно дает sat/vB, так что просто берем значение
            fee_mb = stats.get('suggested_transaction_fee_per_byte_sat', 0)

            return (f"📡 <b>Статус сети Bitcoin:</b>\n\n"
                    f"📈 <b>Транзакций в мемпуле:</b> <code>{stats.get('mempool_transactions', 'N/A'):,}</code>\n\n"
                    f"💸 <b>Рекомендуемая комиссия:</b>\n"
                    f"  - 🚶‍♂️ Средняя: <code>{fee_mb} sat/vB</code>")
        
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching BTC network status: {e}")
            return "❌ Произошла непредвиденная ошибка при получении статуса сети BTC."
