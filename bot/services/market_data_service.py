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

    async def _fetch_json(self, url: str) -> Dict:
        """
        Вспомогательная асинхронная функция для выполнения GET-запроса и получения JSON.
        Вызывает исключение в случае неудачного запроса или не-JSON ответа.
        """
        log.debug(f"Выполнение запроса к URL: {url}")
        try:
            async with self.session.get(url, timeout=10) as response:
                response.raise_for_status()  # Вызовет исключение для статусов 4xx/5xx
                data = await response.json()
                log.debug(f"Получен сырой JSON от {url}: {data}")
                return data
        except aiohttp.ClientError as e:
            log.error(f"Сетевая ошибка при запросе к {url}: {e}")
            raise
        except asyncio.TimeoutError:
            log.error(f"Тайм-аут при запросе к {url}")
            raise
        except Exception as e:
            log.error(f"Неожиданная ошибка при обработке запроса к {url}: {e}")
            raise

    @alru_cache(ttl=600)
    async def get_btc_price_usd(self) -> Optional[float]:
        """
        Получает текущую цену BTC в USD.
        Использует CryptoCompare как основной источник и mempool.space как резервный.
        Результат кэшируется на 10 минут.
        """
        # Попытка 1: Основной источник - CryptoCompare
        try:
            url = "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD"
            data = await self._fetch_json(url)
            price = float(data["USD"])
            log.info(f"Цена BTC/USD (CryptoCompare): ${price:.2f}")
            return price
        except Exception as e:
            log.warning(
                f"Не удалось получить цену от CryptoCompare: {e}. "
                f"Переключение на резервный источник (mempool.space)."
            )

        # Попытка 2: Резервный источник - mempool.space
        try:
            url = "https://mempool.space/api/v1/prices"
            data = await self._fetch_json(url)
            price = float(data.get("BTC", {}).get("USD", 0))
            log.info(f"Цена BTC/USD (mempool.space): ${price:.2f}")
            return price
        except Exception as e_fallback:
            log.error(f"Все источники цен недоступны. Ошибка резервного источника: {e_fallback}")
            return None

    @alru_cache(ttl=600)
    async def get_network_hashrate_ths(self) -> Optional[float]:
        """
        Рассчитывает текущий хешрейт сети Bitcoin в TH/s на основе сложности.
        Использует mempool.space как единственный источник.
        Результат кэшируется на 10 минут.
        """
        try:
            url = "https://mempool.space/api/v1/difficulty-adjustment"
            data = await self._fetch_json(url)
            difficulty = float(data["difficulty"])

            # Формула: hashrate = difficulty * 2^32 / 600
            # 600 секунд - целевое время нахождения блока в сети Bitcoin
            hashrate_hs = (difficulty * (2**32)) / 600
            hashrate_ths = hashrate_hs / 1e12  # Конвертация из H/s в TH/s

            # Валидация полученного значения
            if not (MIN_NETWORK_HASHRATE_THS <= hashrate_ths <= MAX_NETWORK_HASHRATE_THS):
                log.error(f"Рассчитанный хешрейт {hashrate_ths:.2f} TH/s выходит за пределы допустимого диапазона.")
                return None

            log.info(f"Хешрейт сети (рассчитан по сложности): {hashrate_ths / 1e6:.2f} EH/s")
            return hashrate_ths
        except Exception as e:
            log.error(f"Не удалось рассчитать хешрейт сети: {e}")
            return None

    @alru_cache(ttl=600)
    async def get_block_reward_btc(self) -> Optional[float]:
        """
        Получает награду за последний блок (субсидия + комиссии).
        Использует mempool.space для получения данных о последнем блоке.
        Результат кэшируется на 10 минут.
        """
        try:
            # Шаг 1: Получить хеш последнего блока
            tip_hash_url = "https://mempool.space/api/blocks/tip/hash"
            async with self.session.get(tip_hash_url, timeout=10) as response:
                response.raise_for_status()
                latest_block_hash = await response.text()
                log.debug(f"Хеш последнего блока: {latest_block_hash}")

            # Шаг 2: Получить детали блока по хешу
            block_details_url = f"https://mempool.space/api/block/{latest_block_hash}"
            block_data = await self._fetch_json(block_details_url)
            
            # Сумма комиссий в сатоши
            total_fees_satoshi = int(block_data.get("extras", {}).get("totalFees", 0))
            fees_btc = total_fees_satoshi / 1e8  # Конвертация в BTC

            # Полная награда = субсидия + комиссии
            total_reward_btc = CURRENT_BLOCK_SUBSIDY_BTC + fees_btc

            # Валидация
            if not (CURRENT_BLOCK_SUBSIDY_BTC <= total_reward_btc <= MAX_BLOCK_REWARD_BTC):
                log.error(f"Рассчитанная награда за блок {total_reward_btc:.8f} BTC выходит за пределы допустимого диапазона.")
                return None

            log.info(f"Награда за последний блок: {total_reward_btc:.8f} BTC (Субсидия: {CURRENT_BLOCK_SUBSIDY_BTC}, Комиссии: {fees_btc:.8f})")
            return total_reward_btc
        except Exception as e:
            log.error(f"Не удалось получить награду за блок: {e}")
            return None

    @alru_cache(ttl=600)
    async def get_usd_rub_rate(self) -> Optional[float]:
        """
        Получает текущий курс USD/RUB.
        Использует CoinGecko как основной источник и mempool.space как резервный.
        Результат кэшируется на 10 минут.
        """
        # Попытка 1: Основной источник - CoinGecko
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub"
            data = await self._fetch_json(url)
            rate = float(data.get("usd", {}).get("rub", 0))
            if rate <= 0:
                raise ValueError("Неверный курс от CoinGecko")
            log.info(f"Курс USD/RUB (CoinGecko): {rate:.2f}")
            return rate
        except Exception as e:
            log.warning(
                f"Не удалось получить курс от CoinGecko: {e}. "
                f"Переключение на резервный источник."
            )

        # Попытка 2: Резервный источник - mempool.space (если доступно)
        try:
            url = "https://mempool.space/api/v1/prices"  # Проверка наличия курса, если есть
            data = await self._fetch_json(url)
            # Предполагаем, что mempool.space может дать косвенные данные или нет
            rate = float(data.get("USD", {}).get("RUB", 0)) if "USD" in data else 0
            if rate <= 0:
                raise ValueError("Неверный курс от mempool.space")
            log.info(f"Курс USD/RUB (mempool.space): {rate:.2f}")
            return rate
        except Exception as e_fallback:
            log.error(f"Все источники курса недоступны. Ошибка резервного источника: {e_fallback}")
            return None

# Пример использования (для демонстрации и тестирования)
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    async with aiohttp.ClientSession() as session:
        service = MarketDataService(session)
        
        # Параллельное выполнение всех запросов
        price, hashrate, reward, rate = await asyncio.gather(
            service.get_btc_price_usd(),
            service.get_network_hashrate_ths(),
            service.get_block_reward_btc(),
            service.get_usd_rub_rate()
        )
        
        print("-" * 50)
        if price:
            print(f"Текущая цена BTC: ${price:,.2f}")
        else:
            print("Не удалось получить цену BTC.")
            
        if hashrate:
            print(f"Текущий хешрейт сети: {hashrate:,.2f} TH/s ({hashrate / 1e6:,.2f} EH/s)")
        else:
            print("Не удалось получить хешрейт сети.")
            
        if reward:
            print(f"Награда за последний блок: {reward:.8f} BTC")
        else:
            print("Не удалось получить награду за блок.")
            
        if rate:
            print(f"Курс USD/RUB: {rate:.2f}")
        else:
            print("Не удалось получить курс USD/RUB.")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())