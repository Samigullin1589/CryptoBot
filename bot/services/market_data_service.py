# ===============================================================
# Файл: bot/services/market_data_service.py (ИСТИННО ФИНАЛЬНАЯ ВЕРСИЯ)
# Описание: Сервис для получения данных с 3-уровневой системой
# отказоустойчивости на базе трёх независимых API.
# ===============================================================

import asyncio
import logging
from typing import Optional, Dict

import aiohttp
from async_lru import alru_cache

# Настройка логирования
log = logging.getLogger(__name__)

# --- КОНСТАНТЫ ---
MIN_NETWORK_HASHRATE_THS = 100_000_000
MAX_NETWORK_HASHRATE_THS = 10_000_000_000
CURRENT_BLOCK_SUBSIDY_BTC = 3.125
MAX_BLOCK_REWARD_BTC = 10.0
FALLBACK_USD_RUB_RATE = 95.0


class MarketDataService:
    """
    Сервис для получения данных о рынке и сети Bitcoin из внешних API.
    """

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _fetch_json(self, url: str) -> Optional[Dict]:
        log.debug(f"Выполнение JSON-запроса к URL: {url}")
        try:
            async with self.session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            log.error(f"Ошибка при JSON-запросе к {url}: {e}")
            return None

    # --- ОСНОВНЫЕ МЕТОДЫ ПОЛУЧЕНИЯ ДАННЫХ ---
    @alru_cache(ttl=600)
    async def get_btc_price_usd(self) -> Optional[float]:
        log.info("Запрос цены BTC/USD...")
        # Уровень 1: CryptoCompare API
        data = await self._fetch_json("https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD")
        if data and isinstance(data.get("USD"), (int, float)) and data["USD"] > 0:
            price = float(data["USD"])
            log.info(f"УСПЕХ (Уровень 1): Цена BTC/USD (CryptoCompare): ${price:,.2f}")
            return price
        
        # Уровень 2: CoinGecko API
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        if data and data.get("bitcoin", {}).get("usd"):
            price = float(data["bitcoin"]["usd"])
            log.info(f"УСПЕХ (Уровень 2): Цена BTC/USD (CoinGecko): ${price:,.2f}")
            return price
        
        log.error("КРИТИЧЕСКИЙ СБОЙ: Все API-источники цен на BTC недоступны.")
        return None

    @alru_cache(ttl=600)
    async def get_network_hashrate_ths(self) -> Optional[float]:
        log.info("Запрос хешрейта сети...")

        # --- Уровень 1: mempool.space ---
        log.info("Уровень 1: Попытка получить хешрейт через mempool.space...")
        data = await self._fetch_json("https://mempool.space/api/v1/difficulty-adjustment")
        if data and isinstance(data.get("difficulty"), (int, float)) and data["difficulty"] > 0:
            difficulty = float(data["difficulty"])
            hashrate_ths = (difficulty * (2**32)) / 600 / 1e12
            if MIN_NETWORK_HASHRATE_THS <= hashrate_ths <= MAX_NETWORK_HASHRATE_THS:
                log.info(f"УСПЕХ (Уровень 1): Хешрейт сети (mempool.space): {hashrate_ths / 1e6:,.2f} EH/s")
                return hashrate_ths
        log.warning("ОТКАЗ (Уровень 1): API mempool.space недоступен или вернул неверные данные.")

        # --- Уровень 2: Blockchair ---
        log.info("Уровень 2: Попытка получить хешрейт через Blockchair...")
        data = await self._fetch_json("https://api.blockchair.com/bitcoin/stats")
        if data and isinstance(data.get("data", {}).get("hashrate_24h"), (int, float)):
            hashrate_hs = float(data["data"]["hashrate_24h"])
            hashrate_ths = hashrate_hs / 1e12 # Конвертация из H/s в TH/s
            if MIN_NETWORK_HASHRATE_THS <= hashrate_ths <= MAX_NETWORK_HASHRATE_THS:
                log.info(f"УСПЕХ (Уровень 2): Хешрейт сети (Blockchair): {hashrate_ths / 1e6:,.2f} EH/s")
                return hashrate_ths
        log.warning("ОТКАЗ (Уровень 2): API Blockchair недоступен или вернул неверные данные.")
        
        # --- Уровень 3: BTC.com ---
        log.info("Уровень 3: Попытка получить хешрейт через BTC.com...")
        data = await self._fetch_json("https://chain.api.btc.com/v3/block/latest")
        if data and isinstance(data.get('data', {}).get('difficulty'), (int, float)) and data['data']['difficulty'] > 0:
            difficulty = float(data['data']['difficulty'])
            hashrate_ths = (difficulty * (2**32)) / 600 / 1e12
            if MIN_NETWORK_HASHRATE_THS <= hashrate_ths <= MAX_NETWORK_HASHRATE_THS:
                log.info(f"УСПЕХ (Уровень 3): Хешрейт сети (BTC.com): {hashrate_ths / 1e6:,.2f} EH/s")
                return hashrate_ths
        log.warning("ОТКАЗ (Уровень 3): API BTC.com недоступен или вернул неверные данные.")

        log.error("КРИТИЧЕСКИЙ СБОЙ: Все API-источники хешрейта недоступны.")
        return None

    @alru_cache(ttl=600)
    async def get_block_reward_btc(self) -> Optional[float]:
        log.info("Запрос награды за блок...")
        block_data = await self._fetch_json("https://mempool.space/api/v1/blocks/tip")
        if block_data and 'extras' in block_data:
            total_fees_satoshi = block_data.get("extras", {}).get("totalFees", 0)
            fees_btc = int(total_fees_satoshi) / 1e8
            total_reward_btc = CURRENT_BLOCK_SUBSIDY_BTC + fees_btc
            if CURRENT_BLOCK_SUBSIDY_BTC <= total_reward_btc <= MAX_BLOCK_REWARD_BTC:
                log.info(f"Награда за последний блок: {total_reward_btc:.8f} BTC")
                return total_reward_btc

        log.warning("Не удалось получить данные о комиссиях, использую только субсидию.")
        return CURRENT_BLOCK_SUBSIDY_BTC

    @alru_cache(ttl=3600)
    async def get_usd_rub_rate(self) -> float:
        log.info("Запрос курса USD/RUB...")
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub")
        if data and data.get("usd", {}).get("rub"):
            rate = float(data["usd"]["rub"])
            log.info(f"Курс USD/RUB (CoinGecko): {rate:.2f}")
            return rate
        
        log.error(f"Источник курса USD/RUB недоступен. Возвращаю резервный курс: {FALLBACK_USD_RUB_RATE}")
        return FALLBACK_USD_RUB_RATE
