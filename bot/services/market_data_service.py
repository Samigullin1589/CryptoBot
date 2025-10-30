# bot/services/market_data_service.py
import asyncio
from typing import Dict, List, Optional
from loguru import logger
import aiohttp
from bot.utils.http_client import HTTPClient


class MarketDataService:
    """Сервис для получения рыночных данных с множественных источников"""

    PROVIDERS = {
        "binance": {"url": "https://api.binance.com/api/v3/ticker/price", "priority": 1},
        "coinbase": {"url": "https://api.coinbase.com/v2/exchange-rates", "priority": 2},
        "kraken": {"url": "https://api.kraken.com/0/public/Ticker", "priority": 3},
        "cryptocompare": {
            "url": "https://min-api.cryptocompare.com/data/price",
            "priority": 4,
        },
        "coingecko": {
            "url": "https://api.coingecko.com/api/v3/simple/price",
            "priority": 5,
        },
    }

    COIN_MAPPING = {
        "btc": {"binance": "BTCUSDT", "coinbase": "BTC", "kraken": "XXBTZUSD", "symbol": "BTC"},
        "eth": {"binance": "ETHUSDT", "coinbase": "ETH", "kraken": "XETHZUSD", "symbol": "ETH"},
        "ltc": {"binance": "LTCUSDT", "coinbase": "LTC", "kraken": "XLTCZUSD", "symbol": "LTC"},
        "xrp": {"binance": "XRPUSDT", "coinbase": "XRP", "kraken": "XXRPZUSD", "symbol": "XRP"},
        "doge": {"binance": "DOGEUSDT", "coinbase": "DOGE", "kraken": "XDGUSD", "symbol": "DOGE"},
        "ada": {"binance": "ADAUSDT", "coinbase": "ADA", "kraken": "ADAUSD", "symbol": "ADA"},
        "dot": {"binance": "DOTUSDT", "coinbase": "DOT", "kraken": "DOTUSD", "symbol": "DOT"},
        "matic": {"binance": "MATICUSDT", "coinbase": "MATIC", "kraken": "MATICUSD", "symbol": "MATIC"},
        "sol": {"binance": "SOLUSDT", "coinbase": "SOL", "kraken": "SOLUSD", "symbol": "SOL"},
        "avax": {"binance": "AVAXUSDT", "coinbase": "AVAX", "kraken": "AVAXUSD", "symbol": "AVAX"},
        "link": {"binance": "LINKUSDT", "coinbase": "LINK", "kraken": "LINKUSD", "symbol": "LINK"},
        "atom": {"binance": "ATOMUSDT", "coinbase": "ATOM", "kraken": "ATOMUSD", "symbol": "ATOM"},
        "uni": {"binance": "UNIUSDT", "coinbase": "UNI", "kraken": "UNIUSD", "symbol": "UNI"},
        "xlm": {"binance": "XLMUSDT", "coinbase": "XLM", "kraken": "XXLMZUSD", "symbol": "XLM"},
        "bch": {"binance": "BCHUSDT", "coinbase": "BCH", "kraken": "BCHUSD", "symbol": "BCH"},
        "etc": {"binance": "ETCUSDT", "coinbase": "ETC", "kraken": "XETCZUSD", "symbol": "ETC"},
        "trx": {"binance": "TRXUSDT", "coinbase": "TRX", "kraken": "TRXUSD", "symbol": "TRX"},
        "eos": {"binance": "EOSUSDT", "coinbase": "EOS", "kraken": "EOSUSD", "symbol": "EOS"},
        "bnb": {"binance": "BNBUSDT", "coinbase": "BNB", "kraken": "BNBUSD", "symbol": "BNB"},
    }

    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 30
        self.last_fetch = {}
        self._session_cache: Optional[aiohttp.ClientSession] = None
        logger.info("Сервис MarketDataService инициализирован.")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить сессию из http_client"""
        if self._session_cache is None or self._session_cache.closed:
            self._session_cache = await self.http_client._get_session()
        return self._session_cache

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Получить цены для списка монет с fallback на множество провайдеров"""
        result = {}

        for coin_id in coin_ids:
            price = await self._get_price_with_fallback(coin_id)
            result[coin_id] = price

        return result

    async def _get_price_with_fallback(self, coin_id: str) -> Optional[float]:
        """Получить цену с автоматическим переключением между провайдерами"""

        # Проверка кэша
        if coin_id in self.cache:
            cache_entry = self.cache[coin_id]
            if (
                asyncio.get_event_loop().time() - cache_entry.get("timestamp", 0)
            ) < self.cache_ttl:
                return cache_entry.get("price")

        # Попытка получить данные от всех провайдеров по приоритету
        providers = sorted(self.PROVIDERS.items(), key=lambda x: x[1]["priority"])

        for provider_name, provider_config in providers:
            try:
                price = await self._fetch_from_provider(provider_name, coin_id)
                if price:
                    # Кэшируем результат
                    self.cache[coin_id] = {
                        "price": price,
                        "timestamp": asyncio.get_event_loop().time(),
                        "provider": provider_name,
                    }
                    logger.debug(
                        f"Получена цена {coin_id} от {provider_name}: ${price}"
                    )
                    return price
            except Exception as e:
                logger.debug(
                    f"Провайдер {provider_name} недоступен для {coin_id}: {e}"
                )
                continue

        logger.warning(
            f"Не удалось получить цену для {coin_id} ни от одного провайдера"
        )
        return None

    async def _fetch_from_provider(
        self, provider: str, coin_id: str
    ) -> Optional[float]:
        """Получить цену от конкретного провайдера"""

        if coin_id not in self.COIN_MAPPING:
            logger.warning(f"Неизвестная монета: {coin_id}")
            return None

        coin_data = self.COIN_MAPPING[coin_id]

        if provider == "binance":
            return await self._fetch_binance(coin_data.get("binance"))
        elif provider == "coinbase":
            return await self._fetch_coinbase(coin_data.get("coinbase"))
        elif provider == "kraken":
            return await self._fetch_kraken(coin_data.get("kraken"))
        elif provider == "cryptocompare":
            return await self._fetch_cryptocompare(coin_data.get("symbol"))
        elif provider == "coingecko":
            return await self._fetch_coingecko(coin_id)

        return None

    async def _fetch_binance(self, symbol: str) -> Optional[float]:
        """Binance API"""
        if not symbol:
            return None

        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['binance']['url']}?symbol={symbol}"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("price", 0))
        except Exception as e:
            logger.debug(f"Binance error for {symbol}: {e}")
        return None

    async def _fetch_coinbase(self, currency: str) -> Optional[float]:
        """Coinbase API"""
        if not currency:
            return None

        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['coinbase']['url']}?currency=USD"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates = data.get("data", {}).get("rates", {})
                    rate = rates.get(currency)
                    if rate:
                        return 1.0 / float(rate)
        except Exception as e:
            logger.debug(f"Coinbase error for {currency}: {e}")
        return None

    async def _fetch_kraken(self, pair: str) -> Optional[float]:
        """Kraken API"""
        if not pair:
            return None

        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['kraken']['url']}?pair={pair}"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("error"):
                        return None
                    result = data.get("result", {})
                    for key, value in result.items():
                        price = value.get("c", [None])[0]
                        if price:
                            return float(price)
        except Exception as e:
            logger.debug(f"Kraken error for {pair}: {e}")
        return None

    async def _fetch_cryptocompare(self, symbol: str) -> Optional[float]:
        """CryptoCompare API"""
        if not symbol:
            return None

        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['cryptocompare']['url']}?fsym={symbol}&tsyms=USD"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("USD", 0))
        except Exception as e:
            logger.debug(f"CryptoCompare error for {symbol}: {e}")
        return None

    async def _fetch_coingecko(self, coin_id: str) -> Optional[float]:
        """CoinGecko API (последний fallback)"""
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['coingecko']['url']}?ids={coin_id}&vs_currencies=usd"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get(coin_id, {}).get("usd", 0))
        except Exception as e:
            logger.debug(f"CoinGecko error for {coin_id}: {e}")
        return None

    async def get_btc_network_status(self) -> Optional[Dict]:
        """Получить статус сети Bitcoin"""
        try:
            session = await self._get_session()
            # Используем blockchain.info API
            url = "https://blockchain.info/stats?format=json"
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "difficulty": data.get("difficulty"),
                        "hash_rate": data.get("hash_rate"),
                        "blocks_count": data.get("n_blocks_total"),
                        "next_retarget": data.get("nextretarget"),
                    }
        except Exception as e:
            logger.error(f"Ошибка получения статуса BTC сети: {e}")

        return None

    def clear_cache(self):
        """Очистить кэш"""
        self.cache.clear()
        logger.info("Кэш цен очищен")