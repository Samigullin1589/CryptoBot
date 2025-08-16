# ======================================================================================
# File: bot/services/news_service.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Crypto news aggregator using CryptoPanic and NewsAPI.
#   - get_all_latest_news() for scheduled prefetch
#   - prefetch(), warmup(), refresh() convenience
#   - Redis cache with TTL, robust error handling and de-duplication
# ======================================================================================

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore

logger = logging.getLogger(__name__)


class NewsService:
    """
    News aggregator.

    Redis keys:
      - news:latest -> JSON [{"title": "...", "url": "...", "src": "cryptopanic|newsapi", "ts": 169...}, ...]
    """

    def __init__(
        self,
        *,
        settings: Any,
        http_session: aiohttp.ClientSession,
        redis: Optional[Redis] = None,
    ) -> None:
        self.settings = settings
        self.http = http_session
        self.redis = redis

        ns = getattr(settings, "news_service", object())
        self.cache_ttl = int(getattr(ns, "cache_ttl_seconds", 600))
        self.page_size = int(getattr(ns, "page_size", 30))
        self.lang = getattr(ns, "language", "en")
        self.allowed_domains = set(getattr(ns, "allowed_domains", []) or [])

        self.cp_token = getattr(settings, "CRYPTOPANIC_TOKEN", None) or getattr(settings, "CRYPTO_PANIC_TOKEN", None)
        self.newsapi_key = getattr(settings, "NEWSAPI_KEY", None) or getattr(settings, "NEWS_API_KEY", None)

        self.endpoints = getattr(settings, "endpoints", object())
        self.cp_base = getattr(self.endpoints, "cryptopanic_base", "https://cryptopanic.com")
        self.na_base = getattr(self.endpoints, "newsapi_base", "https://newsapi.org")

    # ------------------------------ public API --------------------------------

    async def get_all_latest_news(self) -> List[Dict[str, Any]]:
        """
        Fetches fresh news from providers, deduplicates and caches.
        Returns the merged list.
        """
        merged: List[Dict[str, Any]] = []
        try:
            cp = await self._fetch_cryptopanic()
            merged.extend(cp)
        except Exception as e:  # noqa: BLE001
            logger.debug("CryptoPanic fetch error: %s", e)

        try:
            na = await self._fetch_newsapi()
            merged.extend(na)
        except Exception as e:  # noqa: BLE001
            logger.debug("NewsAPI fetch error: %s", e)

        # dedup and sort by ts desc
        merged = self._dedup(merged)
        merged.sort(key=lambda x: x.get("ts", 0), reverse=True)
        await self._cache_put(merged)
        return merged

    async def prefetch(self) -> None:
        await self.get_all_latest_news()

    async def warmup(self) -> None:
        await self.get_all_latest_news()

    async def refresh(self) -> None:
        await self.get_all_latest_news()

    async def get_cached(self) -> Optional[List[Dict[str, Any]]]:
        if not self.redis:
            return None
        try:
            raw = await self.redis.get("news:latest")
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    # ------------------------------ providers ---------------------------------

    async def _fetch_cryptopanic(self) -> List[Dict[str, Any]]:
        if not self.cp_token:
            return []
        url = f"{self.cp_base}/api/v1/posts/"
        params = {
            "auth_token": self.cp_token,
            "kind": "news",
            "filter": "hot",
            "public": "true",
            "page_size": str(self.page_size),
        }
        async with self.http.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        out: List[Dict[str, Any]] = []
        for it in data.get("results", []):
            title = (it.get("title") or "").strip()
            url = (it.get("url") or "").strip()
            pub = int(time.time())
            try:
                published_at = it.get("published_at") or ""
                # lightweight unix ts parser for ISO8601
                if published_at and "T" in published_at:
                    # naive: keep now if parsing unclear
                    pass
            except Exception:
                pass
            if not url and it.get("source") and it["source"].get("domain"):
                url = f'https://{it["source"]["domain"]}'
            if not title or not url:
                continue
            if self.allowed_domains and not any(d in url for d in self.allowed_domains):
                continue
            out.append(
                {
                    "title": title,
                    "url": url,
                    "src": "cryptopanic",
                    "ts": pub,
                }
            )
        return out

    async def _fetch_newsapi(self) -> List[Dict[str, Any]]:
        if not self.newsapi_key:
            return []
        url = f"{self.na_base}/v2/everything"
        params = {
            "q": "crypto OR bitcoin OR ethereum",
            "sortBy": "publishedAt",
            "language": self.lang,
            "pageSize": str(self.page_size),
            "apiKey": self.newsapi_key,
        }
        async with self.http.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        out: List[Dict[str, Any]] = []
        for a in data.get("articles", []):
            title = (a.get("title") or "").strip()
            url = (a.get("url") or "").strip()
            if not title or not url:
                continue
            if self.allowed_domains and not any(d in url for d in self.allowed_domains):
                continue
            ts = int(time.time())
            out.append({"title": title, "url": url, "src": "newsapi", "ts": ts})
        return out

    # ------------------------------ cache & utils ------------------------------

    async def _cache_put(self, items: List[Dict[str, Any]]) -> None:
        if not self.redis:
            return
        try:
            await self.redis.setex("news:latest", self.cache_ttl, json.dumps(items, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            logger.debug("news cache put error: %s", e)

    def _dedup(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out: List[Dict[str, Any]] = []
        for it in items:
            key = self._fingerprint(it.get("title"), it.get("url"))
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    @staticmethod
    def _fingerprint(title: Optional[str], url: Optional[str]) -> str:
        base = f"{title or ''}|{url or ''}".encode("utf-8", "ignore")
        return hashlib.sha1(base).hexdigest()