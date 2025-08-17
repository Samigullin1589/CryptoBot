# ======================================================================================
# Файл: bot/services/moderation_service.py
# Версия: 2025-08-17
# ======================================================================================

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from redis.asyncio import Redis

from bot.config.settings import Settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _prefix(settings: Settings) -> str:
    return (
        getattr(settings, "redis_prefix", None)
        or getattr(settings, "project_slug", None)
        or "bot"
    )


@dataclass
class BanRecord:
    user_id: int
    by_id: int
    reason: Optional[str]
    created_at: str  # iso
    until: Optional[str]  # iso or None (permanent)

    @property
    def is_permanent(self) -> bool:
        return self.until is None


@dataclass
class MuteRecord:
    user_id: int
    by_id: int
    reason: Optional[str]
    created_at: str
    until: Optional[str]


class ModerationService:
    def __init__(
        self,
        *,
        redis: Redis,
        settings: Settings,
        bot: Any | None = None,
        user_service: Any | None = None,
        admin_service: Any | None = None,
        stop_word_service: Any | None = None,
        config: Any | None = None,
    ) -> None:
        self.redis = redis
        self.settings = settings
        self.bot = bot
        self.user_service = user_service
        self.admin_service = admin_service
        self.stop_word_service = stop_word_service
        self.config = config

        self._pfx = _prefix(settings)

    # ---------- BAN ----------

    def _ban_key(self, user_id: int) -> str:
        return f"{self._pfx}:mod:ban:{user_id}"

    async def ban(
        self,
        user_id: int,
        *,
        by_id: int,
        reason: Optional[str] = None,
        duration: Optional[timedelta] = None,
    ) -> BanRecord:
        created = _utc_now()
        until = None if duration is None else (created + duration)

        rec = BanRecord(
            user_id=user_id,
            by_id=by_id,
            reason=reason,
            created_at=created.isoformat(),
            until=None if until is None else until.isoformat(),
        )

        key = self._ban_key(user_id)
        data = json.dumps(asdict(rec), ensure_ascii=False)
        if duration is None:
            await self.redis.set(key, data)  # без TTL
        else:
            ttl = int(duration.total_seconds())
            ttl = max(ttl, 1)
            await self.redis.setex(key, ttl, data)

        logger.info("BAN set user_id=%s by=%s duration=%s reason=%r", user_id, by_id, duration, reason)
        return rec

    async def unban(self, user_id: int) -> bool:
        res = await self.redis.delete(self._ban_key(user_id))
        logger.info("UNBAN user_id=%s -> %s", user_id, bool(res))
        return bool(res)

    async def is_banned(self, user_id: int) -> bool:
        return await self.redis.exists(self._ban_key(user_id)) == 1

    async def get_ban(self, user_id: int) -> Optional[BanRecord]:
        raw = await self.redis.get(self._ban_key(user_id))
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return BanRecord(**obj)
        except Exception:
            logger.warning("Corrupted ban record for user_id=%s", user_id)
            return None

    # ---------- MUTE ----------

    def _mute_key(self, user_id: int) -> str:
        return f"{self._pfx}:mod:mute:{user_id}"

    async def mute(
        self,
        user_id: int,
        *,
        by_id: int,
        reason: Optional[str] = None,
        duration: Optional[timedelta] = None,
    ) -> MuteRecord:
        created = _utc_now()
        until = None if duration is None else (created + duration)

        rec = MuteRecord(
            user_id=user_id,
            by_id=by_id,
            reason=reason,
            created_at=created.isoformat(),
            until=None if until is None else until.isoformat(),
        )

        key = self._mute_key(user_id)
        data = json.dumps(asdict(rec), ensure_ascii=False)
        if duration is None:
            await self.redis.set(key, data)
        else:
            ttl = int(duration.total_seconds())
            ttl = max(ttl, 1)
            await self.redis.setex(key, ttl, data)

        logger.info("MUTE set user_id=%s by=%s duration=%s reason=%r", user_id, by_id, duration, reason)
        return rec

    async def unmute(self, user_id: int) -> bool:
        res = await self.redis.delete(self._mute_key(user_id))
        logger.info("UNMUTE user_id=%s -> %s", user_id, bool(res))
        return bool(res)

    async def is_muted(self, user_id: int) -> bool:
        return await self.redis.exists(self._mute_key(user_id)) == 1

    async def get_mute(self, user_id: int) -> Optional[MuteRecord]:
        raw = await self.redis.get(self._mute_key(user_id))
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return MuteRecord(**obj)
        except Exception:
            logger.warning("Corrupted mute record for user_id=%s", user_id)
            return None