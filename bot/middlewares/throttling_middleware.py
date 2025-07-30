# =================================================================================
# Файл: bot/middlewares/throttling_middleware.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ИСПРАВЛЕНА)
# =================================================================================
import asyncio
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message

from bot.config.settings import settings # <<< ИСПРАВЛЕНИЕ ЗДЕСЬ

THROTTLE_LUA_SCRIPT = """
-- ... (содержимое LUA-скрипта остается без изменений) ...
"""

class ThrottlingMiddleware(BaseMiddleware):
    """
    Простой middleware для защиты от флуда с использованием LUA-скрипта в Redis.
    """
    def __init__(self, storage: RedisStorage):
        self.storage = storage
        # Используем исправленные пути к настройкам
        self.rate_limit = settings.throttling.rate_limit
        self.user_rate_limit = settings.throttling.user_rate_limit
        self.chat_rate_limit = settings.throttling.chat_rate_limit
        self.script_sha = None

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Если скрипт еще не загружен, загружаем его
        if self.script_sha is None:
            self.script_sha = await self.storage.redis.script_load(THROTTLE_LUA_SCRIPT)

        # Вызываем LUA-скрипт
        is_throttled = await self.storage.redis.evalsha(
            self.script_sha,
            2,
            f"throttle_user:{event.from_user.id}",
            f"throttle_chat:{event.chat.id}",
            self.user_rate_limit,
            self.chat_rate_limit,
            self.rate_limit
        )

        # Если пользователь превысил лимит, просто ничего не делаем
        if is_throttled:
            return

        return await handler(event, data)