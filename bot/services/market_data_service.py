# ===============================================================
# Файл: bot/services/market_data_service.py
# Описание: Сервис для получения данных о рынке и сети Bitcoin, включая курс USD/RUB.
# ===============================================================

import asyncio
import logging
from typing import Optional, Dict

import aiohttp
from async_lru import alru_cache

# Настройка логирования
log = logging.getLogger(__name__)

# Константы для валидации данных
# Минимальный правдоподобный хешрейт сети Bitcoin в TH/s (100 EH/s)
MIN_NETWORK_HASHRATE_THS = 100_000_000
# Максимальный правдоподобный хешрейт сети Bitcoin в TH/s (10 000 EH/s)
MAX_NETWORK_HASHRATE_THS = 10_000_000_000
# Текущая субсидия за блок в BTC
CURRENT_BLOCK_SUBSIDY_BTC = 3.125
# Максимальная ожидаемая награда за блок (субсидия + комиссии)
MAX_BLOCK_REWARD_BTC = 10.0
# Резервный курс на случай полного отказа всех API
FALLBACK_USD_RUB_RATE = 95.0

class MarketDataService:
    """
    Сервис для получения данных о рынке и сети Bitcoin из внешних API.
    Обеспечивает отказоустойчивость за счет кэширования, валидации
    и механизмов резервного переключения.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """
        Инициализация сервиса.
        :param session: Клиентская сессия aiohttp для выполнения HTTP-запросов.
        """
        self.session = session

    async def _fetch_json(self, url: str) -> Optional[Dict]:
        """
        Вспомогательная функция для выполнения GET-запроса и получения JSON.
        Возвращает None в случае любой ошибки.
        """
        log.debug(f"Выполнение запроса к URL: {url}")
        try:
            async with self.session.get(url, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                log.debug(f"Получен сырой JSON от {url}: {data}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            log.error(f"Ошибка при запросе к {url}: {e}")
            return None
        except Exception as e:
            log.error(f"Неожиданная ошибка при обработке запроса к {url}: {e}")
            return None

    @alru_cache(ttl=600)
    async def get_btc_price_usd(self) -> Optional[float]:
        """
        Получает текущую цену BTC в USD. Кэш на 10 минут.
        """
        log.info("Запрос цены BTC/USD...")
        # Источник 1: CryptoCompare
        data = await self._fetch_json("https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD")
        if data and isinstance(data.get("USD"), (int, float)) and data["USD"] > 0:
            price = float(data["USD"])
            log.info(f"Цена BTC/USD (CryptoCompare): ${price:,.2f}")
            return price
        log.warning("Не удалось получить цену от CryptoCompare, переключаюсь на резервный источник.")

        # Источник 2: CoinGecko
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        if data and data.get("bitcoin", {}).get("usd"):
            price = float(data["bitcoin"]["usd"])
            log.info(f"Цена BTC/USD (CoinGecko): ${price:,.2f}")
            return price
        log.error("Все источники цен на BTC недоступны.")
        return None

    @alru_cache(ttl=600)
    async def get_network_hashrate_ths(self) -> Optional[float]:
        """
        Рассчитывает текущий хешрейт сети Bitcoin в TH/s. Кэш на 10 минут.
        """
        log.info("Запрос хешрейта сети...")
        data = await self._fetch_json("https://mempool.space/api/v1/difficulty-adjustment")
        if not data:
            log.error("Не удалось получить данные о сложности сети от mempool.space.")
            return None
        
        difficulty = data.get("difficulty")
        if not isinstance(difficulty, (int, float)) or difficulty <= 0:
            log.error(f"API mempool.space вернул невалидное значение сложности: {difficulty}. Сырой ответ: {data}")
            return None

        # Формула: hashrate = difficulty * 2^32 / 600
        hashrate_hs = (float(difficulty) * (2**32)) / 600
        hashrate_ths = hashrate_hs / 1e12

        if not (MIN_NETWORK_HASHRATE_THS <= hashrate_ths <= MAX_NETWORK_HASHRATE_THS):
            log.error(f"Рассчитанный хешрейт {hashrate_ths:,.2f} TH/s выходит за пределы допустимого диапазона.")
            return None

        log.info(f"Хешрейт сети (рассчитан по сложности): {hashrate_ths / 1e6:,.2f} EH/s")
        return hashrate_ths

    @alru_cache(ttl=600)
    async def get_block_reward_btc(self) -> Optional[float]:
        """
        Получает награду за последний блок (субсидия + комиссии). Кэш на 10 минут.
        """
        log.info("Запрос награды за блок...")
        block_data = await self._fetch_json("https://mempool.space/api/v1/blocks/tip")
        if not block_data or 'extras' not in block_data:
            log.warning("Не удалось получить данные о последнем блоке, использую только субсидию.")
            return CURRENT_BLOCK_SUBSIDY_BTC

        total_fees_satoshi = block_data.get("extras", {}).get("totalFees", 0)
        fees_btc = int(total_fees_satoshi) / 1e8
        total_reward_btc = CURRENT_BLOCK_SUBSIDY_BTC + fees_btc

        if not (CURRENT_BLOCK_SUBSIDY_BTC <= total_reward_btc <= MAX_BLOCK_REWARD_BTC):
            log.error(f"Рассчитанная награда за блок {total_reward_btc:.8f} BTC выходит за пределы диапазона. Возвращаю только субсидию.")
            return CURRENT_BLOCK_SUBSIDY_BTC

        log.info(f"Награда за последний блок: {total_reward_btc:.8f} BTC")
        return total_reward_btc

    @alru_cache(ttl=3600)
    async def get_usd_rub_rate(self) -> float:
        """
        Получает текущий курс USD/RUB. Кэш на 1 час.
        """
        log.info("Запрос курса USD/RUB...")
        # Источник 1: CoinGecko
        data = await self._fetch_json("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub")
        if data and data.get("usd", {}).get("rub"):
            rate = float(data["usd"]["rub"])
            log.info(f"Курс USD/RUB (CoinGecko): {rate:.2f}")
            return rate
        log.warning("Не удалось получить курс от CoinGecko.")
        
        # Если все внешние источники отказали, возвращаем жестко заданный резервный курс
        log.error(f"Все источники курса USD/RUB недоступны. Возвращаю резервный курс: {FALLBACK_USD_RUB_RATE}")
        return FALLBACK_USD_RUB_RATE
