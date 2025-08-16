# ======================================================================================
# File: bot/middlewares/activity_middleware.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Lightweight activity tracker:
#     • Stores last_seen for users and per-chat
#     • Counts messages per user/chat with TTL
#     • Works even if Redis is not configured
# ======================================================================================

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineQuery

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    """
    Сохраняет last_seen и счётчики активности в Redis при наличии.
    Конфигурация не требуется. Если deps.redis отсутствует — просто пропускает.
    """

    def __init__(self, *, ttl_seconds: int = 2 * 24 * 3600) -> None:
        super().__init__()
        self.ttl = int(ttl_seconds)

    async def __call__(self, handler, event: Any, data: Dict[str, Any]) -> Any:  # type: ignore[override]
        deps = data.get("deps")
        r: Optional[Redis] = getattr(deps, "redis", None) if deps else None

        try:
            now = int(time.time())

            if isinstance(event, Message):
                uid = event.from_user.id if event.from_user else None
                chat_id = event.chat.id if event.chat else None
                if r:
                    pipe = r.pipeline()
                    if uid:
                        pipe.setex(f"act:user:last_seen:{uid}", self.ttl, now)
                        pipe.incr(f"act:user:msg_count:{uid}")
                        pipe.expire(f"act:user:msg_count:{uid}", self.ttl)
                    if chat_id:
                        pipe.setex(f"act:chat:last_seen:{chat_id}", self.ttl, now)
                        pipe.incr(f"act:chat:msg_count:{chat_id}")
                        pipe.expire(f"act:chat:msg_count:{chat_id}", self.ttl)
                    await pipe.execute()
            elif isinstance(event, CallbackQuery):
                uid = event.from_user.id if event.from_user else None
                chat_id = event.message.chat.id if event.message and event.message.chat else None
                if r:
                    pipe = r.pipeline()
                    if uid:
                        pipe.setex(f"act:user:last_seen:{uid}", self.ttl, now)
                        pipe.incr(f"act:user:cb_count:{uid}")
                        pipe.expire(f"act:user:cb_count:{uid}", self.ttl)
                    if chat_id:
                        pipe.setex(f"act:chat:last_seen:{chat_id}", self.ttl, now)
                        pipe.incr(f"act:chat:cb_count:{chat_id}")
                        pipe.expire(f"act:chat:cb_count:{chat_id}", self.ttl)
                    await pipe.execute()
            elif isinstance(event, InlineQuery):
                uid = event.from_user.id if event.from_user else None
                if r and uid:
                    await r.setex(f"act:user:last_seen:{uid}", self.ttl, now)

        except Exception as e:  # noqa: BLE001
            # Не блокируем пайплайн из-за аналитики
            logger.debug("ActivityMiddleware error: %s", e)

        return await handler(event, data)