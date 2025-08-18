# ======================================================================================
# File: bot/services/price_service.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Resilient crypto price service with Binance and CoinGecko backends.
#   Caches prices in Redis, supports warmup jobs and batch fetch.
#   Methods recognized by jobs: warmup_cache(), warmup(), prefetch_top(), prefetch().
# ======================================================================================

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Dict, Iterable, List, Optional

import aiohttp

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore

logger = logging.getLogger(__name__)


class PriceService:
    """
    Price provider with Redis cache.

    Redis keys:
      - price:{SYMBOL}:{QUOTE} -> json {"price": float, "ts": int}
      - price:top:symbols -> json ["BTC","ETH",...]
    """

    def __init__(
        self,
        *,
        settings: Any,
        http_session: aiohttp.ClientSession,
        redis: Optional[Redis] = None,
        coin_list_service: Optional[Any] = None,
    ) -> None:
        self.settings = settings
        self.http = http_session
        self.redis = redis
        self.coins = coin_list_service

        ps = getattr(settings, "price_service", object())
        self.default_quote = getattr(ps, "default_quote", "USDT").upper()
        self.cache_ttl = int(getattr(ps, "cache_ttl_seconds", 60))
        self.max_retry = int(getattr(ps, "max_retry", 2))
        self.endpoints = getattr(settings, "endpoints", object())

    # ------------------------------ public API --------------------------------

    async def get_price(self, symbol: str, quote: Optional[str] = None) -> Optional[float]:
        symbol_u = symbol.upper()
        quote_u = (quote or self.default_quote).upper()
        # 1) try cache
        price = await self._cache_get(symbol_u, quote_u)
        if price is not None:
            return price
        # 2) fetch fresh
        price = await self._fetch_price(symbol_u, quote_u)
        if price is not None:
            await self._cache_put(symbol_u, quote_u, price)
        return price

    async def get_prices(self, symbols: Iterable[str], quote: Optional[str] = None) -> Dict[str, Optional[float]]:
        out: Dict[str, Optional[float]] = {}
        for s in symbols:
            out[s.upper()] = await self.get_price(s, quote)
        return out

    async def warmup_cache(self) -> None:
        await self.prefetch_top()

    async def warmup(self) -> None:
        await self.prefetch_top()

    async def prefetch_top(self) -> None:
        """
        Prefetch top symbols either from settings or coin_list_service.
        """
        top = await self._get_top_symbols()
        if not top:
            return
        await self._batch_fetch(top, self.default_quote)

    async def prefetch(self, symbols: List[str], quote: Optional[str] = None) -> None:
        if not symbols:
            return
        await self._batch_fetch(symbols, (quote or self.default_quote).upper())

    # ------------------------------ fetching ----------------------------------

    async def _fetch_price(self, symbol: str, quote: str) -> Optional[float]:
        # Try Binance first
        p = await self._fetch_binance(symbol, quote)
        if p is not None:
            return p
        # Fallback to CoinGecko
        p = await self._fetch_coingecko(symbol, quote)
        return p

    async def _fetch_binance(self, symbol: str, quote: str) -> Optional[float]:
        base = getattr(self.endpoints, "binance_base", "https://api.binance.com")
        pair = f"{symbol}{quote}"
        url = f"{base}/api/v3/ticker/price?symbol={pair}"
        try:
            async with self.http.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
            price = float(data.get("price"))
            if not math.isfinite(price):
                return None
            return price
        except Exception:
            return None

    async def _fetch_coingecko(self, symbol: str, quote: str) -> Optional[float]:
        base = getattr(self.endpoints, "coingecko_base", "https://api.coingecko.com/api/v3")
        # Need CoinGecko coin id; try via coin_list_service index in Redis
        coin_id = None
        try:
            if self.redis:
                coin_id = await self.redis.get(f"coin:index:symbol:{symbol}")
        except Exception:
            coin_id = None
        if not coin_id:
            # as a blunt fallback — try mapping BTC->bitcoin, ETH->ethereum for majors
            mapping = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana", "XRP": "ripple"}
            coin_id = mapping.get(symbol)
            if not coin_id:
                return None
        url = f"{base}/simple/price?ids={coin_id}&vs_currencies={quote.lower()}"
        try:
            async with self.http.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
            val = data.get(coin_id, {}).get(quote.lower())
            return float(val) if val is not None else None
        except Exception:
            return None

    async def _batch_fetch(self, symbols: List[str], quote: str) -> None:
        for s in symbols:
            p = await self._fetch_price(s, quote)
            if p is not None:
                await self._cache_put(s, quote, p)

    async def _get_top_symbols(self) -> List[str]:
        # From settings first
        try:
            top = list(getattr(self.settings.price_service, "top_symbols", []))
            if top:
                return [s.upper() for s in top]
        except Exception:
            pass
        # Else from coin_list_service cache (first dozen by symbol)
        try:
            if self.coins:
                data = await self.coins.get_all()
                if data:
                    return [c["symbol"].upper() for c in data[:20]]
        except Exception:
            pass
        # Fallback majors
        return ["BTC", "ETH", "BNB", "SOL", "XRP"]

    # ------------------------------- cache ------------------------------------

    async def _cache_get(self, symbol: str, quote: str) -> Optional[float]:
        if not self.redis:
            return None
        try:
            j = await self.redis.get(f"price:{symbol}:{quote}")
            if not j:
                return None
            obj = json.loads(j)
            ts = int(obj.get("ts", 0))
            if time.time() - ts > self.cache_ttl:
                return None
            val = obj.get("price")
            return float(val) if val is not None else None
        except Exception:
            return None

    async def _cache_put(self, symbol: str, quote: str, price: float) -> None:
        if not self.redis:
            return
        try:
            val = json.dumps({"price": float(price), "ts": int(time.time())}, ensure_ascii=False)
            await self.redis.setex(f"price:{symbol}:{quote}", self.cache_ttl, val)
        except Exception as e:  # noqa: BLE001
            logger.debug("price cache put error: %s", e)
