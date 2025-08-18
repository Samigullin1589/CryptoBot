# =============================================================================
# File: bot/middlewares/spam_guard_middleware.py
# Purpose: Aiogram v3 middleware that invokes AntiSpamService
# =============================================================================

from __future__ import annotations

from typing import Any
from collections.abc import Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.services.anti_spam_service import AntiSpamService


class SpamGuardMiddleware(BaseMiddleware):
    def __init__(self, anti_spam: AntiSpamService):
        super().__init__()
        self.anti_spam = anti_spam

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Пускаем только входящие сообщения
        if (
            isinstance(event, Message)
            and event.from_user
            and not event.from_user.is_bot
        ):
            verdict = await self.anti_spam.analyze_and_act(event)
            if verdict:  # уже что-то сделали (удалили/замьютили/забанили)
                return  # не пробрасываем дальше хендлерам
        return await handler(event, data)
