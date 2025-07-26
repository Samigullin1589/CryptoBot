# ===============================================================
# Файл: bot/services/market_data_service.py (Версия с веб-скрапингом v2)
# Описание: Сервис для получения данных с 3-уровневой системой отказоустойчивости:
# Уровень 1: Основное API
# Уровень 2: Резервное API
# Уровень 3: Веб-скрапинг как последний рубеж (цель: blockchain.com)
# ===============================================================

# --- НОВЫЕ ЗАВИСИМОСТИ ---
# Перед использованием этого файла, установите необходимые библиотеки:
# pip install beautifulsoup4 lxml
# -------------------------

import asyncio
import logging
import re
from typing import Optional, Dict

import aiohttp
from async_lru import alru_cache
from bs4 import BeautifulSoup, Tag

# Настройка логирования
log = logging.getLogger(__name__)

# --- КОНСТАНТЫ ---
MIN_NETWORK_HASHRATE_THS = 100_000_000
MAX_NETWORK_HASHRATE_THS = 10_000_000_000
CURRENT_BLOCK_SUBSIDY_BTC = 3.125
MAX_BLOCK_REWARD_BTC = 10.0
FALLBACK_USD_RUB_RATE = 95.0
SCRAPING_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Connection': 'keep-alive',
}


class MarketDataService:
    """
    Сервис для получения данных о рынке и сети Bitcoin из внешних API и веб-сайтов.
    """

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ---
    async def _fetch_json(self, url: str) -> Optional[Dict]:
        log.debug(f"Выполнение JSON-запроса к URL: {url}")
        try:
            async with self.session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            log.error(f"Ошибка при JSON-запросе к {url}: {e}")
            return None

    async def _fetch_and_parse_html(self, url: str) -> Optional[BeautifulSoup]:
        log.debug(f"Выполнение HTML-запроса к URL: {url}")
        try:
            async with self.session.get(url, headers=SCRAPING_HEADERS, timeout=15) as response:
                response.raise_for_status()
                html = await response.text()
                return BeautifulSoup(html, 'lxml')
        except Exception as e:
            log.error(f"Ошибка при скрапинге страницы {url}: {e}")
            return None

    # --- МЕТОДЫ ВЕБ-СКРАПИНГА (УРОВЕНЬ 3) ---
    async def _scrape_hashrate_from_blockchain_com(self) -> Optional[float]:
        """
        Извлекает хешрейт с сайта blockchain.com/explorer.
        """
        log.info("Скрапинг хешрейта с blockchain.com...")
        soup = await self._fetch_and_parse_html("https://www.blockchain.com/explorer")
        if not soup:
            return None

        try:
            # Ищем карточку со статистикой, в которой есть текст "Hash Rate"
            hash_rate_card = soup.find(lambda tag: tag.name == 'div' and 'Hash Rate' in tag.text and 'EH/s' in tag.text)
            
            if not hash_rate_card:
                log.error("Не удалось найти карточку 'Hash Rate' на blockchain.com")
                return None

            # Внутри карточки ищем текст, содержащий число и "EH/s"
            hashrate_text = hash_rate_card.get_text(separator=' ', strip=True)
            match = re.search(r'([\d,\.]+)\s*EH/s', hashrate_text)
            
            if not match:
                log.error(f"Не удалось извлечь значение хешрейта из текста: '{hashrate_text}'")
                return None

            value_str = match.group(1).replace(',', '')
            value_ehs = float(value_str)
            
            # Конвертируем EH/s в TH/s (1 EH/s = 1,000,000 TH/s)
            return value_ehs * 1_000_000
        except Exception as e:
            log.error(f"Исключение при парсинге хешрейта с blockchain.com: {e}")
            return None


    # --- ОСНОВНЫЕ МЕТОДЫ ПОЛУЧЕНИЯ ДАННЫХ ---
    @alru_cache(ttl=600)
    async def get_btc_price_usd(self) -> Optional[float]:
        log.info("Запрос цены BTC/USD...")
        # Уровень 1: CryptoCompare API
        data = await self._fetch_json("https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD")
        if data and isinstance(data.get("USD"), (int, float)) and data["USD"] > 0:
            price = float(data["USD"])
            log.info(f"Уровень 1 (API): Цена BTC/USD (CryptoCompare): ${price:,.2f}")
            return price
        
        # Уровень 2: CoinGecko API
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        if data and data.get("bitcoin", {}).get("usd"):
            price = float(data["bitcoin"]["usd"])
            log.info(f"Уровень 2 (API): Цена BTC/USD (CoinGecko): ${price:,.2f}")
            return price
        
        log.error("Все API-источники цен на BTC недоступны.")
        return None

    @alru_cache(ttl=600)
    async def get_network_hashrate_ths(self) -> Optional[float]:
        log.info("Запрос хешрейта сети...")
        # Уровень 1 & 2: mempool.space API
        data = await self._fetch_json("https://mempool.space/api/v1/difficulty-adjustment")
        if data and isinstance(data.get("difficulty"), (int, float)) and data["difficulty"] > 0:
            difficulty = float(data["difficulty"])
            hashrate_ths = (difficulty * (2**32)) / 600 / 1e12
            if MIN_NETWORK_HASHRATE_THS <= hashrate_ths <= MAX_NETWORK_HASHRATE_THS:
                log.info(f"Уровень 1 (API): Хешрейт сети (mempool.space): {hashrate_ths / 1e6:,.2f} EH/s")
                return hashrate_ths

        log.warning("API mempool.space недоступен или вернул неверные данные.")
        # Уровень 3: Веб-скрапинг
        log.info("Переключение на Уровень 3: Веб-скрапинг для хешрейта.")
        scraped_hashrate = await self._scrape_hashrate_from_blockchain_com()
        if scraped_hashrate and MIN_NETWORK_HASHRATE_THS <= scraped_hashrate <= MAX_NETWORK_HASHRATE_THS:
             log.info(f"Уровень 3 (Скрапинг): Хешрейт сети (blockchain.com): {scraped_hashrate / 1e6:,.2f} EH/s")
             return scraped_hashrate
        
        log.error("Все источники хешрейта (API и скрапинг) недоступны.")
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

        log.warning("Не удалось получить данные о последнем блоке, использую только субсидию.")
        return CURRENT_BLOCK_SUBSIDY_BTC

    @alru_cache(ttl=3600)
    async def get_usd_rub_rate(self) -> float:
        log.info("Запрос курса USD/RUB...")
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub")
        if data and data.get("usd", {}).get("rub"):
            rate = float(data["usd"]["rub"])
            log.info(f"Курс USD/RUB (CoinGecko): {rate:.2f}")
            return rate
        
        log.error(f"Все источники курса USD/RUB недоступны. Возвращаю резервный курс: {FALLBACK_USD_RUB_RATE}")
        return FALLBACK_USD_RUB_RATE
