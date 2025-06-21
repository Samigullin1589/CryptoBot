import asyncio
import logging
from typing import Optional, Dict

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class MarketDataService:
    @alru_cache(maxsize=1, ttl=14400)
    async def get_fear_and_greed_index(self) -> Optional[Dict]:
        logger.info("Fetching Fear & Greed Index...")
        async with aiohttp.ClientSession() as session:
            if settings.cmc_api_key:
                headers = {'X-CMC_PRO_API_KEY': settings.cmc_api_key}
                data = await make_request(session, settings.cmc_fear_and_greed_url, headers=headers)
                if data and 'data' in data:
                    logger.info("Fetched F&G index from CoinMarketCap")
                    fng_data = data['data']['fear_greed_historical'][-1]
                    return {
                        'value': fng_data['score'],
                        'value_classification': fng_data['rating']
                    }
                logger.warning("Failed to fetch from CMC, falling back to Alternative.me")
            data = await make_request(session, settings.fear_and_greed_api_url)
            if data and 'data' in data and data['data']:
                logger.info("Fetched F&G index from Alternative.me")
                return data['data'][0]
        logger.error("Failed to fetch F&G index from all sources.")
        return None

    @alru_cache(maxsize=1, ttl=43200)
    async def get_usd_rub_rate(self) -> float:
        logger.info("Fetching USD/RUB exchange rate.")
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, settings.cbr_daily_json_url)
            if data and "Valute" in data and "USD" in data["Valute"]:
                rate = data["Valute"]["USD"]["Value"]
                logger.info(f"Current USD/RUB rate: {rate}")
                return float(rate)
        logger.warning("Using fallback USD/RUB rate.")
        return 90.0

    async def get_halving_info(self) -> str:
        logger.info("Fetching Bitcoin halving info...")
        async with aiohttp.ClientSession() as s:
            height_str = await make_request(s, "https://mempool.space/api/blocks/tip/height", response_type='text')
            if not height_str or not height_str.isdigit():
                return "❌ Не удалось получить данные о халвинге."
            
            current_block = int(height_str)
            halving_interval = 210000
            blocks_left = halving_interval - (current_block % halving_interval)
            days_left = blocks_left / 144
            
            return (f"⏳ <b>До халвинга Bitcoin осталось:</b>\n\n"
                    f"🧱 <b>Блоков:</b> <code>{blocks_left:,}</code>\n"
                    f"🗓 <b>Примерно дней:</b> <code>{days_left:.1f}</code>")

    async def get_btc_network_status(self) -> str:
        logger.info("Fetching Bitcoin network status...")
        async with aiohttp.ClientSession() as s:
            urls = [
                "https://mempool.space/api/v1/fees/recommended",
                "https://mempool.space/api/mempool"
            ]
            tasks = [make_request(s, url) for url in urls]
            results = await asyncio.gather(*tasks)
            fees_data, mempool_data = results

            if not fees_data or not mempool_data:
                return "❌ Не удалось получить статус сети BTC."
            
            return (f"📡 <b>Статус сети Bitcoin:</b>\n\n"
                    f"📈 <b>Транзакций в мемпуле:</b> <code>{mempool_data.get('count', 'N/A'):,}</code>\n\n"
                    f"💸 <b>Рекомендуемые комиссии (sat/vB):</b>\n"
                    f"  - 🚀 Высокий: <code>{fees_data.get('fastestFee', 'N/A')}</code>\n"
                    f"  - 🚶‍♂️ Средний: <code>{fees_data.get('halfHourFee', 'N/A')}</code>\n"
                    f"  - 🐢 Низкий: <code>{fees_data.get('hourFee', 'N/A')}</code>")