# ===============================================================
# Файл: bot/services/market_data_service.py (АЛЬФА-РЕШЕНИЕ)
# Описание: Использует https://api.blockchain.info/q/hashrate для
# хешрейта и https://blockchain.info/latestblock для награды,
# исключая фиксированные значения.
# ===============================================================

import asyncio
import logging
from typing import Optional, Dict

import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

# --- ИСТОЧНИКИ ДАННЫХ ---
BLOCKCHAIN_INFO_BLOCK_COUNT_URL = "https://blockchain.info/q/getblockcount"
BLOCKCHAIR_BTC_STATS_URL = "https://api.blockchair.com/bitcoin/stats"
CRYPTOCOMPARE_BASE_URL = "https://min-api.cryptocompare.com/data"
MEMPOOL_SPACE_HASH_RATE_URL = "https://mempool.space/api/v1/mining/hashrate/1w"
BLOCKCHAIN_INFO_HASH_RATE_URL = "https://api.blockchain.info/q/hashrate"
BLOCKCHAIN_INFO_LATEST_BLOCK_URL = "https://blockchain.info/latestblock"

class MarketDataService:
    def __init__(self, http_session: aiohttp.ClientSession):
        self.http_session = http_session
        self.cryptocompare_api_key = settings.cryptocompare_api_key

    @alru_cache(maxsize=10, ttl=600)
    async def get_coin_network_data(self, coin_symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Получает ключевые данные о сети монеты (хешрейт, награда за блок) и ее цену.
        Использует CryptoCompare для цены и Blockchain.com для хешрейта и награды.
        force_refresh: принудительно обновляет данные, игнорируя кэш.
        """
        symbol = coin_symbol.upper()
        logger.info(f"Fetching network data and price for {symbol}... (force_refresh={force_refresh})")

        if not self.cryptocompare_api_key:
            logger.error("CryptoCompare API key is missing. Mining calculator will not work correctly.")
            return None

        headers = {"authorization": f"Apikey {self.cryptocompare_api_key}"}
        price_url = f"{CRYPTOCOMPARE_BASE_URL}/price?fsym={symbol}&tsyms=USD"

        try:
            # Получение цены из CryptoCompare
            price_data = await make_request(self.http_session, price_url, headers=headers)
            logger.info(f"Raw CryptoCompare price data for {symbol}: {price_data}")

            if not price_data or "USD" not in price_data:
                logger.error(f"Invalid price data response from CryptoCompare for {symbol}: {price_data}")
                return None

            price = float(price_data["USD"])

            # Получение хешрейта из Blockchain.com
            hashrate_data = await make_request(self.http_session, BLOCKCHAIN_INFO_HASH_RATE_URL, response_type='text')
            logger.info(f"Raw Blockchain.com hashrate data for {symbol}: {hashrate_data}")
            if not hashrate_data or not hashrate_data.strip():
                logger.error("Failed to fetch hashrate data from Blockchain.com.")
                return None

            network_hashrate_ths = float(hashrate_data) / 1e12  # Конверсия из H/s в TH/s
            logger.info(f"Using Blockchain.com hashrate: {network_hashrate_ths} TH/s")

            # Получение награды за блок из Blockchain.com
            latest_block = await make_request(self.http_session, BLOCKCHAIN_INFO_LATEST_BLOCK_URL)
            logger.info(f"Raw latest block data: {latest_block}")
            if not latest_block or "reward" not in latest_block:
                logger.error("Failed to fetch block reward data from Blockchain.com.")
                return None

            block_reward = float(latest_block["reward"]) / 1e8  # Конверсия из сатоши в BTC
            logger.info(f"Using Blockchain.com block reward: {block_reward} BTC")

            if network_hashrate_ths <= 0 or block_reward <= 0:
                logger.error(f"Zero hashrate or block reward for {symbol} from Blockchain.com. Calculation may fail.")
                return None

            return {
                "price": price,
                "network_hashrate": network_hashrate_ths,
                "block_reward": block_reward
            }

        except Exception as e:
            logger.exception(f"Failed to fetch data for {symbol}: {e}")
            return None

    @alru_cache(maxsize=1, ttl=14400)
    async def get_fear_and_greed_index(self) -> Optional[dict]:
        logger.info("Fetching Fear & Greed Index...")
        if settings.cmc_api_key:
            headers = {'X-CMC_PRO_API_KEY': settings.cmc_api_key}
            data = await make_request(self.http_session, "https://pro-api.coinmarketcap.com/v1/crypto/fng", headers=headers)
            if data and 'data' in data and data['data']:
                fng_data = data['data'][0]
                logger.info("Fetched F&G index from CoinMarketCap")
                return {'value': fng_data['score'], 'value_classification': fng_data['rating']}
            logger.warning("Failed to fetch from CMC, falling back to Alternative.me")
        
        data = await make_request(self.http_session, settings.fear_and_greed_api_url)
        if data and 'data' in data and data['data']:
            logger.info("Fetched F&G index from Alternative.me")
            return data['data'][0]
        
        logger.error("Failed to fetch F&G index from all sources.")
        return None

    @alru_cache(maxsize=1, ttl=43200)
    async def get_usd_rub_rate(self) -> float:
        logger.info("Fetching USD/RUB exchange rate.")
        data = await make_request(self.http_session, settings.cbr_daily_json_url)
        if data and "Valute" in data and "USD" in data["Valute"]:
            rate = data["Valute"]["USD"]["Value"]
            logger.info(f"Current USD/RUB rate: {rate}")
            return float(rate)
        logger.warning("Could not fetch USD/RUB rate. Using fallback rate 90.0.")
        return 90.0

    async def get_halving_info(self) -> str:
        logger.info("Fetching Bitcoin halving info from blockchain.info...")
        current_block = None
        height_str = await make_request(self.http_session, BLOCKCHAIN_INFO_BLOCK_COUNT_URL, response_type='text', timeout=7)
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
        logger.info("Fetching Bitcoin network status from blockchair.com...")
        try:
            data = await make_request(self.http_session, BLOCKCHAIR_BTC_STATS_URL, timeout=7)
            if not data or "data" not in data:
                logger.error("Failed to fetch BTC network status from blockchair.com, response has invalid structure.")
                return "❌ Не удалось получить статус сети BTC. Внешний сервис вернул неверные данные."
            
            stats = data["data"]
            fee_mb = stats.get('suggested_transaction_fee_per_byte_sat', 0)

            return (f"📡 <b>Статус сети Bitcoin:</b>\n\n"
                    f"📈 <b>Транзакций в мемпуле:</b> <code>{stats.get('mempool_transactions', 'N/A'):,}</code>\n\n"
                    f"💸 <b>Рекомендуемая комиссия:</b>\n"
                    f"  - 🚶‍♂️ Средняя: <code>{fee_mb} sat/vB</code>")
        
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching BTC network status: {e}")
            return "❌ Произошла непредвиденная ошибка при получении статуса сети BTC."