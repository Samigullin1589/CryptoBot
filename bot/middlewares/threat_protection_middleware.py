# bot/middlewares/threat_protection_middleware.py
from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, ContentType

class ThreatProtectionMiddleware(BaseMiddleware):
    """
    Middleware that inspects incoming messages and calls SecurityService.
    If a message is considered spam, it can be deleted, user warned, muted or banned.
    """

    def __init__(self, security_service, moderation_service, settings):
        super().__init__()
        self.sec = security_service
        self.mod = moderation_service
        self.settings = settings

    async def __call__(self, handler: Callable[[Message, Dict[str, Any]], Any], event: Message, data: Dict[str, Any]) -> Any:  # type: ignore[override]
        message: Message = event

        # Fast skip channels/bots if wanted
        if message.from_user and message.from_user.is_bot:
            return await handler(event, data)

        # Inspect
        try:
            verdict = await self.sec.inspect_message(message)
        except Exception:
            # Never block whole chat if inspection fails
            return await handler(event, data)

        action = verdict.get("action")
        if not action:
            return await handler(event, data)

        # Apply action
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None

        if action == "delete":
            with contextlib.suppress(Exception):
                await message.delete()
            return  # stop propagation

        if action == "warn" and user_id:
            with contextlib.suppress(Exception):
                await message.reply(verdict.get("reason", "Нарушение правил. Будьте внимательнее."))
            with contextlib.suppress(Exception):
                await message.delete()
            return

        if action == "mute" and user_id:
            with contextlib.suppress(Exception):
                await self.mod.mute_user(chat_id, user_id, minutes=verdict.get("minutes", 60), reason=verdict.get("reason", "Mute by anti-spam"))
            with contextlib.suppress(Exception):
                await message.delete()
            return

        if action == "ban" and user_id:
            with contextlib.suppress(Exception):
                await self.mod.ban_user(admin_id=user_id, target_user_id=user_id, target_chat_id=chat_id, reason=verdict.get("reason", "Autoban by anti-spam"))
            with contextlib.suppress(Exception):
                await message.delete()
            return

        # Default: just pass
        return await handler(event, data)