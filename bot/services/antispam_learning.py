# bot/services/antispam_learning.py
from __future__ import annotations

import asyncio
from typing import Iterable, List, Tuple, Optional
from dataclasses import dataclass
from rapidfuzz import fuzz

try:
    # redis-py >= 4.2
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = object  # type: ignore


@dataclass
class ScoredPhrase:
    phrase: str
    score: float


class AntiSpamLearning:
    """
    Self-learning phrase/domain memory backed by Redis.
    Stores phrases and domains that admins marked as spam, and
    can score new texts against that memory using RapidFuzz.
    """

    def __init__(self, redis: "Redis", ns: str = "antispam"):
        self.r = redis
        self.ns = ns

    # Redis keys
    def k_phrases(self) -> str: return f"{self.ns}:phrases"       # ZSET phrase -> weight
    def k_domains(self) -> str:  return f"{self.ns}:domains"       # ZSET domain -> weight
    def k_samples(self) -> str:  return f"{self.ns}:samples"       # LIST latest N full texts

    async def add_feedback(
        self,
        text: str,
        domains: Iterable[str] | None = None,
        weight: float = 1.0,
        keep_samples: int = 5000,
    ) -> None:
        """
        Add spam feedback: stores key phrases and domains with weight.
        Very lightweight and safe to call from admin actions.
        """
        text = (text or "").strip()
        if not text:
            return

        # crude phrase extraction: keep long tokens / bi-grams by whitespace
        tokens = [t for t in text.split() if len(t) >= 5][:50]
        phrases = set(tokens)

        # Additionally add 2-grams (simple join of adjacent tokens)
        for i in range(len(tokens) - 1):
            two = f"{tokens[i]} {tokens[i+1]}"
            if 8 <= len(two) <= 64:
                phrases.add(two)

        if phrases:
            pipe = self.r.pipeline()
            for p in phrases:
                pipe.zincrby(self.k_phrases(), weight, p.lower())
            # keep only top 5000 phrases
            pipe.zremrangebyrank(self.k_phrases(), 0, -(5000 + 1))  # noop if less
            pipe.lpush(self.k_samples(), text[:2000])
            pipe.ltrim(self.k_samples(), 0, keep_samples - 1)
            await pipe.execute()

        if domains:
            pipe = self.r.pipeline()
            for d in domains:
                pipe.zincrby(self.k_domains(), weight, d.lower())
            pipe.zremrangebyrank(self.k_domains(), 0, -(2000 + 1))
            await pipe.execute()

    async def score_text(
        self,
        text: str,
        min_ratio: int = 85,
        top_k: int = 1000,
    ) -> Tuple[int, Optional[ScoredPhrase]]:
        """
        Compare text against memory phrases using rapidfuzz ratio.
        Returns (best_ratio, best_phrase) where best_phrase may be None.
        """
        text = (text or "").strip().lower()
        if not text:
            return 0, None

        # Fetch top phrases from Redis
        phrases = await self.r.zrevrange(self.k_phrases(), 0, top_k - 1, withscores=False)  # type: ignore[arg-type]
        best_ratio = 0
        best_phrase: Optional[ScoredPhrase] = None

        for p in phrases:
            p = p.decode("utf-8") if isinstance(p, (bytes, bytearray)) else str(p)
            ratio = fuzz.partial_ratio(text, p)
            if ratio > best_ratio:
                best_ratio = ratio
                best_phrase = ScoredPhrase(p, float(ratio))

        if best_ratio < min_ratio:
            return best_ratio, None
        return best_ratio, best_phrase

    async def is_bad_domain(self, host: str, min_score: float = 1.0) -> bool:
        if not host:
            return False
        score = await self.r.zscore(self.k_domains(), host.lower())
        return (score or 0.0) >= min_score