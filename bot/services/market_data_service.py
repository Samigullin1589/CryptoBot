# ===============================================================
# Файл: bot/services/market_data_service.py (ОКОНЧАТЕЛЬНЫЙ FIX)
# Описание: Исправлена ошибка с регистром при обращении к
# 'settings.cryptocompare_api_key'. Улучшена обработка hashrate
# с принудительным обновлением, усиленной диагностикой и
# резервным источником mempool.space.
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

class MarketDataService:
    def __init__(self, http_session: aiohttp.ClientSession):
        self.http_session = http_session
        # --- ИСПРАВЛЕНО: Обращаемся к полю в нижнем регистре, как в settings.py ---
        self.cryptocompare_api_key = settings.cryptocompare_api_key
        # --------------------------------------------------------------------

    @alru_cache(maxsize=10, ttl=600)
    async def get_coin_network_data(self, coin_symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Получает ключевые данные о сети монеты (хешрейт, награда за блок) и ее цену.
        Использует CryptoCompare API с резервным источником для hashrate.
        force_refresh: принудительно обновляет данные, игнорируя кэш.
        """
        symbol = coin_symbol.upper()
        logger.info(f"Fetching network data and price for {symbol} from CryptoCompare... (force_refresh={force_refresh})")

        if not self.cryptocompare_api_key:
            logger.error("CryptoCompare API key is missing. Mining calculator will not work correctly.")
            return None

        headers = {"authorization": f"Apikey {self.cryptocompare_api_key}"}
        network_url = f"{CRYPTOCOMPARE_BASE_URL}/blockchain/latest?fsym={symbol}"
        price_url = f"{CRYPTOCOMPARE_BASE_URL}/price?fsym={symbol}&tsyms=USD"

        try:
            async with asyncio.TaskGroup() as tg:
                network_task = tg.create_task(make_request(self.http_session, network_url, headers=headers))
                price_task = tg.create_task(make_request(self.http_session, price_url, headers=headers))

            network_data = network_task.result()
            price_data = price_task.result()

            logger.info(f"Raw CryptoCompare network data for {symbol}: {network_data}")
            logger.info(f"Raw CryptoCompare price data for {symbol}: {price_data}")

            if not network_data or "Data" not in network_data or network_data.get("Response") == "Error":
                logger.error(f"Invalid network data response for {symbol}: {network_data}")
                return None
            
            if not price_data or "USD" not in price_data:
                logger.error(f"Invalid price data response for {symbol}: {price_data}")
                return None

            net_info = network_data["Data"]
            logger.info(f"Available keys in net_info: {list(net_info.keys())}")  # Диагностика ключей
            price = float(price_data["USD"])
            # Явное извлечение и приведение hashrate
            hashrate_value = net_info.get("hashrate")
            if hashrate_value is None or str(hashrate_value).lower() == "null" or hashrate_value == 0:
                hashrate_value = net_info.get("hash_rate", 0)
            try:
                network_hashrate = float(hashrate_value) / 1e12 if hashrate_value else 0  # Конверсия из H/s в TH/s
            except (ValueError, TypeError):
                logger.warning(f"Invalid hashrate value for {symbol}: {hashrate_value} (type: {type(hashrate_value)})")
                network_hashrate = 0

            logger.info(f"Raw hashrate value for {symbol}: {hashrate_value} (type: {type(hashrate_value)})")
            logger.info(f"Converted hashrate for {symbol}: {network_hashrate} TH/s")

            # Резервный источник для hashrate, если равно 0
            if network_hashrate == 0 and symbol == "BTC":
                logger.warning("Zero hashrate from CryptoCompare. Fetching from mempool.space...")
                mempool_data = await make_request(self.http_session, MEMPOOL_SPACE_HASH_RATE_URL)
                logger.info(f"Raw mempool.space data: {mempool_data}")
                if mempool_data and "currentHashrate" in mempool_data:
                    try:
                        network_hashrate = float(mempool_data["currentHashrate"]) / 1e12  # Конверсия в TH/s
                        logger.info(f"Using mempool.space hashrate: {network_hashrate} TH/s")
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid hashrate from mempool.space: {mempool_data['currentHashrate']}")

            block_reward = float(net_info.get("block_reward", 0))

            if network_hashrate == 0:
                logger.error(f"Zero hashrate for {symbol} after all sources. Calculation may fail.")
                return None

            return {
                "price": price,
                "network_hashrate": network_hashrate,
                "block_reward": block_reward
            }

        except Exception as e:
            logger.exception(f"Failed to fetch data for {symbol} from CryptoCompare: {e}")
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