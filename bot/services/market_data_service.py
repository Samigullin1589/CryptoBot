# bot/services/market_data_service.py
import asyncio
from typing import Dict, List, Optional, Tuple
from loguru import logger
import aiohttp
from bot.utils.http_client import HTTPClient


class MarketDataService:
    """Сервис для получения рыночных данных с множественных источников"""

    PROVIDERS = {
        "binance": {"url": "https://api.binance.com/api/v3/ticker/price", "priority": 1, "requires_key": False},
        "bybit": {"url": "https://api.bybit.com/v5/market/tickers", "priority": 2, "requires_key": False},
        "kucoin": {"url": "https://api.kucoin.com/api/v1/market/allTickers", "priority": 3, "requires_key": False},
        "gateio": {"url": "https://api.gateio.ws/api/v4/spot/tickers", "priority": 4, "requires_key": False},
        "coinbase": {"url": "https://api.coinbase.com/v2/exchange-rates", "priority": 5, "requires_key": False},
        "kraken": {"url": "https://api.kraken.com/0/public/Ticker", "priority": 6, "requires_key": False},
        "coincap": {"url": "https://api.coincap.io/v2/assets", "priority": 7, "requires_key": False},
        "cryptocompare": {"url": "https://min-api.cryptocompare.com/data/price", "priority": 8, "requires_key": False},
        "coingecko": {"url": "https://api.coingecko.com/api/v3/simple/price", "priority": 9, "requires_key": False},
    }

    COIN_MAPPING = {
        "btc": {
            "binance": "BTCUSDT", "bybit": "BTCUSDT", "kucoin": "BTC-USDT", "gateio": "BTC_USDT",
            "coinbase": "BTC", "kraken": "XXBTZUSD", "coincap": "bitcoin", "symbol": "BTC"
        },
        "eth": {
            "binance": "ETHUSDT", "bybit": "ETHUSDT", "kucoin": "ETH-USDT", "gateio": "ETH_USDT",
            "coinbase": "ETH", "kraken": "XETHZUSD", "coincap": "ethereum", "symbol": "ETH"
        },
        "bnb": {
            "binance": "BNBUSDT", "bybit": "BNBUSDT", "kucoin": "BNB-USDT", "gateio": "BNB_USDT",
            "coinbase": "BNB", "kraken": "BNBUSD", "coincap": "binance-coin", "symbol": "BNB"
        },
        "sol": {
            "binance": "SOLUSDT", "bybit": "SOLUSDT", "kucoin": "SOL-USDT", "gateio": "SOL_USDT",
            "coinbase": "SOL", "kraken": "SOLUSD", "coincap": "solana", "symbol": "SOL"
        },
        "xrp": {
            "binance": "XRPUSDT", "bybit": "XRPUSDT", "kucoin": "XRP-USDT", "gateio": "XRP_USDT",
            "coinbase": "XRP", "kraken": "XXRPZUSD", "coincap": "ripple", "symbol": "XRP"
        },
        "ada": {
            "binance": "ADAUSDT", "bybit": "ADAUSDT", "kucoin": "ADA-USDT", "gateio": "ADA_USDT",
            "coinbase": "ADA", "kraken": "ADAUSD", "coincap": "cardano", "symbol": "ADA"
        },
        "doge": {
            "binance": "DOGEUSDT", "bybit": "DOGEUSDT", "kucoin": "DOGE-USDT", "gateio": "DOGE_USDT",
            "coinbase": "DOGE", "kraken": "XDGUSD", "coincap": "dogecoin", "symbol": "DOGE"
        },
        "dot": {
            "binance": "DOTUSDT", "bybit": "DOTUSDT", "kucoin": "DOT-USDT", "gateio": "DOT_USDT",
            "coinbase": "DOT", "kraken": "DOTUSD", "coincap": "polkadot", "symbol": "DOT"
        },
        "trx": {
            "binance": "TRXUSDT", "bybit": "TRXUSDT", "kucoin": "TRX-USDT", "gateio": "TRX_USDT",
            "coinbase": "TRX", "kraken": "TRXUSD", "coincap": "tron", "symbol": "TRX"
        },
        "matic": {
            "binance": "MATICUSDT", "bybit": "MATICUSDT", "kucoin": "MATIC-USDT", "gateio": "MATIC_USDT",
            "coinbase": "MATIC", "kraken": "MATICUSD", "coincap": "polygon", "symbol": "MATIC"
        },
        "ltc": {
            "binance": "LTCUSDT", "bybit": "LTCUSDT", "kucoin": "LTC-USDT", "gateio": "LTC_USDT",
            "coinbase": "LTC", "kraken": "XLTCZUSD", "coincap": "litecoin", "symbol": "LTC"
        },
        "avax": {
            "binance": "AVAXUSDT", "bybit": "AVAXUSDT", "kucoin": "AVAX-USDT", "gateio": "AVAX_USDT",
            "coinbase": "AVAX", "kraken": "AVAXUSD", "coincap": "avalanche", "symbol": "AVAX"
        },
        "link": {
            "binance": "LINKUSDT", "bybit": "LINKUSDT", "kucoin": "LINK-USDT", "gateio": "LINK_USDT",
            "coinbase": "LINK", "kraken": "LINKUSD", "coincap": "chainlink", "symbol": "LINK"
        },
        "atom": {
            "binance": "ATOMUSDT", "bybit": "ATOMUSDT", "kucoin": "ATOM-USDT", "gateio": "ATOM_USDT",
            "coinbase": "ATOM", "kraken": "ATOMUSD", "coincap": "cosmos", "symbol": "ATOM"
        },
        "uni": {
            "binance": "UNIUSDT", "bybit": "UNIUSDT", "kucoin": "UNI-USDT", "gateio": "UNI_USDT",
            "coinbase": "UNI", "kraken": "UNIUSD", "coincap": "uniswap", "symbol": "UNI"
        },
        "xlm": {
            "binance": "XLMUSDT", "bybit": "XLMUSDT", "kucoin": "XLM-USDT", "gateio": "XLM_USDT",
            "coinbase": "XLM", "kraken": "XXLMZUSD", "coincap": "stellar", "symbol": "XLM"
        },
        "bch": {
            "binance": "BCHUSDT", "bybit": "BCHUSDT", "kucoin": "BCH-USDT", "gateio": "BCH_USDT",
            "coinbase": "BCH", "kraken": "BCHUSD", "coincap": "bitcoin-cash", "symbol": "BCH"
        },
        "etc": {
            "binance": "ETCUSDT", "bybit": "ETCUSDT", "kucoin": "ETC-USDT", "gateio": "ETC_USDT",
            "coinbase": "ETC", "kraken": "XETCZUSD", "coincap": "ethereum-classic", "symbol": "ETC"
        },
        "eos": {
            "binance": "EOSUSDT", "bybit": "EOSUSDT", "kucoin": "EOS-USDT", "gateio": "EOS_USDT",
            "coinbase": "EOS", "kraken": "EOSUSD", "coincap": "eos", "symbol": "EOS"
        },
    }

    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 30
        self._session_cache: Optional[aiohttp.ClientSession] = None
        logger.info("Сервис MarketDataService инициализирован.")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить сессию из http_client"""
        if self._session_cache is None or self._session_cache.closed:
            self._session_cache = await self.http_client._get_session()
        return self._session_cache

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Получить цены для списка монет с параллельными запросами"""
        result = {}
        
        # Параллельные запросы для всех монет
        tasks = [self._get_price_with_fallback(coin_id) for coin_id in coin_ids]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        for coin_id, price in zip(coin_ids, prices):
            if isinstance(price, Exception):
                logger.error(f"Ошибка получения цены {coin_id}: {price}")
                result[coin_id] = None
            else:
                result[coin_id] = price

        return result

    async def _get_price_with_fallback(self, coin_id: str) -> Optional[float]:
        """Получить цену с автоматическим переключением между провайдерами"""

        # Проверка кэша
        if coin_id in self.cache:
            cache_entry = self.cache[coin_id]
            if (asyncio.get_event_loop().time() - cache_entry.get("timestamp", 0)) < self.cache_ttl:
                return cache_entry.get("price")

        # Попытка получить данные от всех провайдеров параллельно (первые 3)
        providers = sorted(self.PROVIDERS.items(), key=lambda x: x[1]["priority"])[:3]
        
        tasks = [self._fetch_from_provider(pname, coin_id) for pname, _ in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Берем первый успешный результат
        for (pname, _), result in zip(providers, results):
            if isinstance(result, (int, float)) and result > 0:
                self.cache[coin_id] = {
                    "price": result,
                    "timestamp": asyncio.get_event_loop().time(),
                    "provider": pname,
                }
                logger.debug(f"Получена цена {coin_id} от {pname}: ${result}")
                return result
        
        # Если первые 3 не сработали, пробуем остальные последовательно
        for provider_name, provider_config in providers[3:]:
            try:
                price = await self._fetch_from_provider(provider_name, coin_id)
                if price and price > 0:
                    self.cache[coin_id] = {
                        "price": price,
                        "timestamp": asyncio.get_event_loop().time(),
                        "provider": provider_name,
                    }
                    logger.debug(f"Получена цена {coin_id} от {provider_name}: ${price}")
                    return price
            except Exception as e:
                logger.debug(f"Провайдер {provider_name} недоступен для {coin_id}: {e}")
                continue

        logger.warning(f"Не удалось получить цену для {coin_id} ни от одного провайдера")
        return None

    async def _fetch_from_provider(self, provider: str, coin_id: str) -> Optional[float]:
        """Получить цену от конкретного провайдера"""

        if coin_id not in self.COIN_MAPPING:
            return None

        coin_data = self.COIN_MAPPING[coin_id]

        try:
            if provider == "binance":
                return await self._fetch_binance(coin_data.get("binance"))
            elif provider == "bybit":
                return await self._fetch_bybit(coin_data.get("bybit"))
            elif provider == "kucoin":
                return await self._fetch_kucoin(coin_data.get("kucoin"))
            elif provider == "gateio":
                return await self._fetch_gateio(coin_data.get("gateio"))
            elif provider == "coinbase":
                return await self._fetch_coinbase(coin_data.get("coinbase"))
            elif provider == "kraken":
                return await self._fetch_kraken(coin_data.get("kraken"))
            elif provider == "coincap":
                return await self._fetch_coincap(coin_data.get("coincap"))
            elif provider == "cryptocompare":
                return await self._fetch_cryptocompare(coin_data.get("symbol"))
            elif provider == "coingecko":
                return await self._fetch_coingecko(coin_id)
        except Exception as e:
            logger.debug(f"Error fetching from {provider}: {e}")
            
        return None

    async def _fetch_binance(self, symbol: str) -> Optional[float]:
        """Binance API"""
        if not symbol:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['binance']['url']}?symbol={symbol}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("price", 0))
        except Exception as e:
            logger.debug(f"Binance error: {e}")
        return None

    async def _fetch_bybit(self, symbol: str) -> Optional[float]:
        """Bybit API"""
        if not symbol:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['bybit']['url']}?category=spot&symbol={symbol}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tickers = data.get("result", {}).get("list", [])
                    if tickers:
                        return float(tickers[0].get("lastPrice", 0))
        except Exception as e:
            logger.debug(f"Bybit error: {e}")
        return None

    async def _fetch_kucoin(self, symbol: str) -> Optional[float]:
        """KuCoin API"""
        if not symbol:
            return None
        try:
            session = await self._get_session()
            async with session.get(self.PROVIDERS['kucoin']['url'], timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tickers = data.get("data", {}).get("ticker", [])
                    for ticker in tickers:
                        if ticker.get("symbol") == symbol:
                            return float(ticker.get("last", 0))
        except Exception as e:
            logger.debug(f"KuCoin error: {e}")
        return None

    async def _fetch_gateio(self, symbol: str) -> Optional[float]:
        """Gate.io API"""
        if not symbol:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['gateio']['url']}?currency_pair={symbol}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        return float(data[0].get("last", 0))
        except Exception as e:
            logger.debug(f"Gate.io error: {e}")
        return None

    async def _fetch_coinbase(self, currency: str) -> Optional[float]:
        """Coinbase API"""
        if not currency:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['coinbase']['url']}?currency=USD"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates = data.get("data", {}).get("rates", {})
                    rate = rates.get(currency)
                    if rate:
                        return 1.0 / float(rate)
        except Exception as e:
            logger.debug(f"Coinbase error: {e}")
        return None

    async def _fetch_kraken(self, pair: str) -> Optional[float]:
        """Kraken API"""
        if not pair:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['kraken']['url']}?pair={pair}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
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
            logger.debug(f"Kraken error: {e}")
        return None

    async def _fetch_coincap(self, asset_id: str) -> Optional[float]:
        """CoinCap API"""
        if not asset_id:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['coincap']['url']}/{asset_id}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get("data", {}).get("priceUsd")
                    if price:
                        return float(price)
        except Exception as e:
            logger.debug(f"CoinCap error: {e}")
        return None

    async def _fetch_cryptocompare(self, symbol: str) -> Optional[float]:
        """CryptoCompare API"""
        if not symbol:
            return None
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['cryptocompare']['url']}?fsym={symbol}&tsyms=USD"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("USD", 0))
        except Exception as e:
            logger.debug(f"CryptoCompare error: {e}")
        return None

    async def _fetch_coingecko(self, coin_id: str) -> Optional[float]:
        """CoinGecko API (последний fallback)"""
        try:
            session = await self._get_session()
            url = f"{self.PROVIDERS['coingecko']['url']}?ids={coin_id}&vs_currencies=usd"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get(coin_id, {}).get("usd", 0))
        except Exception as e:
            logger.debug(f"CoinGecko error: {e}")
        return None

    async def get_top_n_coins(self, limit: int = 100) -> List[Dict]:
        """Получить топ N монет (заглушка)"""
        return []

    async def get_btc_network_status(self) -> Optional[Dict]:
        """Получить статус сети Bitcoin"""
        try:
            session = await self._get_session()
            url = "https://blockchain.info/stats?format=json"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
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