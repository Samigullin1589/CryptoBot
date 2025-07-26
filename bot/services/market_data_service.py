# ===============================================================
# Файл: bot/services/market_data_service.py (Версия с веб-скрапингом)
# Описание: Сервис для получения данных с 3-уровневой системой отказоустойчивости:
# Уровень 1: Основное API
# Уровень 2: Резервное API
# Уровень 3: Веб-скрапинг как последний рубеж
# ===============================================================

# --- НОВЫЕ ЗАВИСИМОСТИ ---
# Перед использованием этого файла, установите необходимые библиотеки:
# pip install beautifulsoup4 lxml
# -------------------------

import asyncio
import logging
import re
from typing import Optional, Dict, Tuple

import aiohttp
from async_lru import alru_cache
from bs4 import BeautifulSoup

# Настройка логирования
log = logging.getLogger(__name__)

# --- КОНСТАНТЫ ---
# Константы для валидации данных
MIN_NETWORK_HASHRATE_THS = 100_000_000
MAX_NETWORK_HASHRATE_THS = 10_000_000_000
CURRENT_BLOCK_SUBSIDY_BTC = 3.125
MAX_BLOCK_REWARD_BTC = 10.0
FALLBACK_USD_RUB_RATE = 95.0
# Заголовок для скрапинга, чтобы выглядеть как реальный браузер
SCRAPING_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
        """Загружает и парсит HTML-страницу, используя lxml."""
        log.debug(f"Выполнение HTML-запроса к URL: {url}")
        try:
            async with self.session.get(url, headers=SCRAPING_HEADERS, timeout=15) as response:
                response.raise_for_status()
                html = await response.text()
                # Используем 'lxml' как более быстрый и надежный парсер
                return BeautifulSoup(html, 'lxml')
        except Exception as e:
            log.error(f"Ошибка при скрапинге страницы {url}: {e}")
            return None

    # --- МЕТОДЫ ВЕБ-СКРАПИНГА (УРОВЕНЬ 3) ---
    async def _scrape_hashrate_from_btc_com(self) -> Optional[float]:
        """
        Извлекает хешрейт с сайта btc.com.
        Это более хрупкий метод, используется как последний резерв.
        """
        log.info("Скрапинг хешрейта с btc.com...")
        soup = await self._fetch_and_parse_html("https://btc.com/btc")
        if not soup:
            return None

        try:
            # Ищем заголовок "Hashrate", чтобы найти соответствующее ему значение.
            # Это надежнее, чем искать по CSS-классу, который может измениться.
            hashrate_title_element = soup.find('dt', string=re.compile(r'Hashrate'))
            if not hashrate_title_element:
                log.error("Не удалось найти элемент с заголовком 'Hashrate' на btc.com")
                return None
            
            # Значение хешрейта находится в следующем за заголовком теге <dd>
            hashrate_value_element = hashrate_title_element.find_next_sibling('dd')
            if not hashrate_value_element:
                log.error("Не удалось найти элемент со значением хешрейта на btc.com")
                return None

            hashrate_text = hashrate_value_element.text.strip() # Пример: "650.12 EH/s"
            value_match = re.search(r'[\d\.]+', hashrate_text)
            if not value_match:
                return None

            value = float(value_match.group(0))
            if 'EH/s' in hashrate_text:
                return value * 1_000_000 # Конвертируем EH/s в TH/s
            elif 'PH/s' in hashrate_text:
                 return value * 1_000 # Конвертируем PH/s в TH/s
            
            log.error(f"Неизвестные единицы измерения хешрейта на btc.com: {hashrate_text}")
            return None
        except Exception as e:
            log.error(f"Исключение при парсинге хешрейта с btc.com: {e}")
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
        return None # В данном примере не добавляем скрапинг для цены, чтобы не усложнять

    @alru_cache(ttl=600)
    async def get_network_hashrate_ths(self) -> Optional[float]:
        log.info("Запрос хешрейта сети...")
        # Уровень 1 & 2: mempool.space API (считается надежным)
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
        scraped_hashrate = await self._scrape_hashrate_from_btc_com()
        if scraped_hashrate and MIN_NETWORK_HASHRATE_THS <= scraped_hashrate <= MAX_NETWORK_HASHRATE_THS:
             log.info(f"Уровень 3 (Скрапинг): Хешрейт сети (btc.com): {scraped_hashrate / 1e6:,.2f} EH/s")
             return scraped_hashrate
        
        log.error("Все источники хешрейта (API и скрапинг) недоступны.")
        return None

    @alru_cache(ttl=600)
    async def get_block_reward_btc(self) -> Optional[float]:
        log.info("Запрос награды за блок...")
        # mempool.space API
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
        # CoinGecko API
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub")
        if data and data.get("usd", {}).get("rub"):
            rate = float(data["usd"]["rub"])
            log.info(f"Курс USD/RUB (CoinGecko): {rate:.2f}")
            return rate
        
        log.error(f"Все источники курса USD/RUB недоступны. Возвращаю резервный курс: {FALLBACK_USD_RUB_RATE}")
        return FALLBACK_USD_RUB_RATE

