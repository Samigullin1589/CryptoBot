# ======================================================================================
# File: bot/middlewares/activity_middleware.py
# Version: "Distinguished Engineer" — MAX Build (Aug 16, 2025)
# Description:
#   Lightweight activity tracker:
#     • Stores last_seen for users and per-chat
#     • Counts messages per user/chat with TTL
#     • Exposes simple Redis schema for analytics & anti-raid heuristics
# ======================================================================================

from __future__ import annotations

import logging
from typing import Any, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    def __init__(
        self,
        deps: Deps,
        *,
        ttl_seconds: int = 14 * 24 * 3600,  # keep stats 14 days
        per_chat_ttl_seconds: int = 7 * 24 * 3600,
        key_prefix: str = "activity",
    ) -> None:
        super().__init__()
        self.deps = deps
        self.ttl = ttl_seconds
        self.chat_ttl = per_chat_ttl_seconds
        self.px = key_prefix.strip(":")

    async def __call__(self, handler, event: Union[Message, CallbackQuery], data: Dict[str, Any]):
        r = self.deps.redis

        try:
            # Extract actor & chat
            if isinstance(event, Message):
                uid = event.from_user.id if event.from_user else None
                chat_id = event.chat.id if event.chat else None
                ts = int(event.date.timestamp()) if event.date else None
            else:
                uid = event.from_user.id if event.from_user else None
                chat_id = event.message.chat.id if (event.message and event.message.chat) else None
                ts = int(event.message.date.timestamp()) if (event.message and event.message.date) else None

            if uid:
                # last seen (global)
                k_user = f"{self.px}:user:{uid}:last_seen"
                await r.set(k_user, ts or 0, ex=self.ttl)

                # per-user counters
                k_cnt = f"{self.px}:user:{uid}:cnt"
                await r.incr(k_cnt)
                await r.expire(k_cnt, self.ttl)

            if uid and chat_id:
                # per-chat last seen & counters
                k_uc = f"{self.px}:chat:{chat_id}:user:{uid}:last_seen"
                await r.set(k_uc, ts or 0, ex=self.chat_ttl)

                k_uc_cnt = f"{self.px}:chat:{chat_id}:user:{uid}:cnt"
                await r.incr(k_uc_cnt)
                await r.expire(k_uc_cnt, self.chat_ttl)

                # chat-wide counters
                k_chat_cnt = f"{self.px}:chat:{chat_id}:cnt"
                await r.incr(k_chat_cnt)
                await r.expire(k_chat_cnt, self.chat_ttl)

        except Exception as e:
            logger.debug("ActivityMiddleware store error: %s", e)

        # Pass to next
        return await handler(event, data)