# ======================================================================================
# File: bot/services/coin_list_service.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Unified coin list service with resilient fetching from Binance and CoinGecko.
#   Provides methods required by jobs scheduler:
#     - update_and_index(), refresh_and_index(), refresh_cache()
#     - fetch(), cache(), reindex(), warmup(), get_all()
#   Persists cache & secondary indexes in Redis for fast lookups.
# ======================================================================================

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class _Endpoints:
    binance_base: str = "https://api.binance.com"
    coingecko_base: str = "https://api.coingecko.com/api/v3"


class CoinListService:
    """
    Coin list aggregator.

    Redis keys:
      - coin:list -> JSON [{"id": "...", "symbol": "BTC", "name": "Bitcoin"}...]
      - coin:index:symbol:{SYMBOL} -> coin_id
      - coin:index:id:{COIN_ID} -> SYMBOL
    """

    def __init__(
        self,
        *,
        settings: Any,
        http_session: aiohttp.ClientSession,
        redis: Redis | None = None,
        endpoints: Any | None = None,
    ) -> None:
        self.settings = settings
        self.http = http_session
        self.redis = redis
        self.ttl_seconds = getattr(
            getattr(settings, "coin_list_service", object()), "ttl_seconds", 24 * 3600
        )
        self.max_items = getattr(
            getattr(settings, "coin_list_service", object()), "max_items", 5000
        )
        self.endpoints = _Endpoints(
            binance_base=getattr(
                getattr(settings, "endpoints", object()),
                "binance_base",
                _Endpoints.binance_base,
            ),
            coingecko_base=getattr(
                getattr(settings, "endpoints", object()),
                "coingecko_base",
                _Endpoints.coingecko_base,
            ),
        )

    # ----------------------------- public API ---------------------------------

    async def update_and_index(self) -> list[dict[str, Any]]:
        coins = await self.fetch()
        coins = self._normalize_and_dedup(coins)
        await self.cache(coins)
        await self.reindex(coins)
        return coins

    async def refresh_and_index(self) -> list[dict[str, Any]]:
        return await self.update_and_index()

    async def refresh_cache(self) -> None:
        coins = await self.fetch()
        coins = self._normalize_and_dedup(coins)
        await self.cache(coins)

    async def warmup(self) -> None:
        await self.refresh_cache()

    async def fetch(self) -> list[dict[str, Any]]:
        """
        Try Binance first (fast), then fall back to CoinGecko.
        """
        coins: list[dict[str, Any]] = []
        try:
            b = await self._fetch_from_binance()
            if b:
                coins = b
        except Exception as e:  # noqa: BLE001
            logger.debug("Binance coin fetch failed: %s", e)

        if not coins:
            try:
                g = await self._fetch_from_coingecko()
                if g:
                    coins = g
            except Exception as e:  # noqa: BLE001
                logger.warning("CoinGecko coin fetch failed: %s", e)

        return coins[: self.max_items]

    async def cache(self, coins: list[dict[str, Any]]) -> None:
        if not self.redis:
            return
        try:
            pipe = self.redis.pipeline()
            pipe.setex(
                "coin:list", self.ttl_seconds, json.dumps(coins, ensure_ascii=False)
            )
            await pipe.execute()
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to cache coin list: %s", e)

    async def reindex(self, coins: list[dict[str, Any]] | None = None) -> None:
        if not self.redis:
            return
        if coins is None:
            coins = await self.get_all()

        if coins is None:
            return

        try:
            pipe = self.redis.pipeline()
            # очистим старые индексы по маске — в проде можно хранить в отдельном hset
            # здесь перезапишем актуальные
            for c in coins:
                sym = str(c.get("symbol", "")).upper()
                cid = str(c.get("id", "")).lower()
                if not sym:
                    continue
                pipe.setex(
                    f"coin:index:symbol:{sym}", self.ttl_seconds, cid or sym.lower()
                )
                if cid:
                    pipe.setex(f"coin:index:id:{cid}", self.ttl_seconds, sym)
            await pipe.execute()
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to build coin indexes: %s", e)

    async def get_all(self) -> list[dict[str, Any]] | None:
        if not self.redis:
            return None
        try:
            raw = await self.redis.get("coin:list")
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    # ---------------------------- data sources --------------------------------

    async def _fetch_from_binance(self) -> list[dict[str, Any]]:
        url = f"{self.endpoints.binance_base}/api/v3/exchangeInfo"
        async with self.http.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Binance exchangeInfo status={resp.status}")
            data = await resp.json()
        symbols = data.get("symbols", [])
        # Вытащим уникальные baseAsset как кандидаты на symbol
        uniq = {}
        for s in symbols:
            base = s.get("baseAsset")
            if not base:
                continue
            base_u = str(base).upper()
            if base_u not in uniq:
                uniq[base_u] = {"id": base_u.lower(), "symbol": base_u, "name": base_u}
        return list(uniq.values())

    async def _fetch_from_coingecko(self) -> list[dict[str, Any]]:
        url = f"{self.endpoints.coingecko_base}/coins/list?include_platform=false"
        async with self.http.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"CoinGecko coins/list status={resp.status}")
            data = await resp.json()
        out = []
        for c in data:
            cid = str(c.get("id", "")).lower()
            sym = str(c.get("symbol", "")).upper()
            name = str(c.get("name", "")).strip() or sym
            if sym:
                out.append({"id": cid or sym.lower(), "symbol": sym, "name": name})
        return out

    # ------------------------------ helpers -----------------------------------

    def _normalize_and_dedup(self, coins: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out: list[dict[str, Any]] = []
        for c in coins:
            sym = str(c.get("symbol", "")).upper()
            cid = str(c.get("id", "")).lower() or sym.lower()
            name = str(c.get("name", "")).strip() or sym
            if not sym:
                continue
            key = sym
            if key in seen:
                continue
            seen.add(key)
            out.append({"id": cid, "symbol": sym, "name": name})
        out.sort(key=lambda x: x["symbol"])
        return out
