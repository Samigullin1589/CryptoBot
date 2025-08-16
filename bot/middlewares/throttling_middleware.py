# ======================================================================================
# File: bot/middlewares/throttling_middleware.py
# Version: "Distinguished Engineer" — MAX Build (Aug 16, 2025)
# Description:
#   High-precision throttling (per-user & per-chat) using Redis + Lua.
#   - Works for Message and CallbackQuery
#   - Rate config comes from settings.throttling (user_rate_limit, chat_rate_limit)
#   - Admins (settings.admin_ids) are bypassed
#   - Friendly feedback (toast for callbacks, short message for chats)
# ======================================================================================

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from bot.config.settings import settings
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

# Lua script:
#   Implements minimal interval (ms) between events per key.
#   Returns:
#     {allowed=1, retry_after_ms=0} if allowed
#     {allowed=0, retry_after_ms=...} if too soon
THROTTLE_LUA = """
local key = KEYS[1]
local interval_ms = ARGV[1]
local now_ms = redis.call('TIME')
-- TIME returns array: seconds, microseconds
local ms = (now_ms[1] * 1000) + math.floor(now_ms[2] / 1000)

local last = redis.call('GET', key)
if not last then
  redis.call('SET', key, ms, 'PX', interval_ms)
  return {1, 0}
end

local diff = ms - tonumber(last)
if diff >= tonumber(interval_ms) then
  redis.call('SET', key, ms, 'PX', interval_ms)
  return {1, 0}
else
  return {0, tonumber(interval_ms) - diff}
end
"""


def _compute_interval_ms(rate_per_sec: float) -> int:
    """
    Convert rate (events per second) into minimal interval in milliseconds.
    Example: 2.0 -> 500 ms; 1.0 -> 1000 ms; 0 (or <=0) -> disable throttling.
    """
    if rate_per_sec is None or rate_per_sec <= 0:
        return 0
    return int(max(1.0, 1000.0 / float(rate_per_sec)))


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(
        self,
        deps: Deps,
        *,
        user_rate: Optional[float] = None,
        chat_rate: Optional[float] = None,
        key_prefix: Optional[str] = None,
        exempt_admins: bool = True,
        feedback: bool = True,
    ) -> None:
        super().__init__()
        self.deps = deps
        cfg = settings.throttling
        self.user_interval_ms = _compute_interval_ms(user_rate if user_rate is not None else cfg.user_rate_limit)
        self.chat_interval_ms = _compute_interval_ms(chat_rate if chat_rate is not None else cfg.chat_rate_limit)
        self.key_prefix = (key_prefix or cfg.key_prefix or "throttling").strip(":")
        self.exempt_admins = exempt_admins
        self.feedback = feedback
        self._lua_sha: Optional[str] = None

    async def _ensure_lua(self) -> None:
        if self._lua_sha:
            return
        try:
            self._lua_sha = await self.deps.redis.script_load(THROTTLE_LUA)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning("Failed to load throttling Lua script: %s. Falling back to Python time.", e)
            self._lua_sha = None

    async def _throttle(self, key: str, interval_ms: int) -> Tuple[bool, int]:
        """
        Returns (allowed, retry_after_ms)
        """
        if interval_ms <= 0:
            return True, 0

        r = self.deps.redis
        await self._ensure_lua()
        try:
            if self._lua_sha:
                allowed, retry_after = await r.evalsha(self._lua_sha, 1, key, interval_ms)  # type: ignore[misc]
            else:
                # Fallback: naive throttle using SETNX+PTTL (slightly less precise)
                ok = await r.set(key, "1", nx=True, px=interval_ms)
                if ok:
                    return True, 0
                ttl = await r.pttl(key)
                return False, int(ttl if ttl > 0 else interval_ms)
        except Exception as e:
            logger.debug("Throttle eval error for key=%s: %s", key, e)
            return True, 0

        return bool(allowed), int(retry_after)

    async def __call__(self, handler, event: Union[Message, CallbackQuery], data: Dict[str, Any]):
        # Only Message & CallbackQuery are throttled (others pass)
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        # Admins can be exempted
        try:
            uid = (event.from_user.id if event.from_user else None)
            if self.exempt_admins and uid and uid in (settings.admin_ids or []):
                return await handler(event, data)
        except Exception:
            pass

        # Build keys
        chat_id = None
        if isinstance(event, Message):
            chat_id = event.chat.id if event.chat else None
            uid = event.from_user.id if event.from_user else None
        else:
            chat_id = event.message.chat.id if event.message and event.message.chat else None
            uid = event.from_user.id if event.from_user else None

        # Apply user-level throttle
        if uid and self.user_interval_ms > 0:
            key_u = f"{self.key_prefix}:u:{uid}"
            allowed, retry_ms = await self._throttle(key_u, self.user_interval_ms)
            if not allowed:
                await self._on_throttled(event, retry_ms)
                return

        # Apply chat-level throttle
        if chat_id and self.chat_interval_ms > 0:
            key_c = f"{self.key_prefix}:c:{chat_id}"
            allowed, retry_ms = await self._throttle(key_c, self.chat_interval_ms)
            if not allowed:
                await self._on_throttled(event, retry_ms)
                return

        # Pass to next
        return await handler(event, data)

    async def _on_throttled(self, event: Union[Message, CallbackQuery], retry_ms: int) -> None:
        if not self.feedback:
            return
        retry_s = max(1, int(round(retry_ms / 1000.0)))
        msg = f"⏳ Слишком часто. Подождите ~{retry_s}с."
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=False)
            else:
                m = await event.reply(msg)
                # auto-delete helper message after a short while (best-effort)
                try:
                    await asyncio.sleep(3)
                    await m.delete()
                except Exception:
                    pass
        except Exception:
            pass