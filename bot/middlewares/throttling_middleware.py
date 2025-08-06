# =================================================================================
# Файл: bot/middlewares/throttling_middleware.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Middleware для защиты от флуда с использованием LUA-скрипта в Redis.
# ИСПРАВЛЕНИЕ: Добавлен LUA-скрипт и унифицировано получение настроек.
# =================================================================================
import asyncio
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message

from bot.config.settings import settings

# LUA-скрипт для атомарной проверки и установки лимитов
THROTTLE_LUA_SCRIPT = """
    -- KEYS[1]: ключ для пользователя (e.g., throttle_user:12345)
    -- KEYS[2]: ключ для чата (e.g., throttle_chat:54321)
    -- ARGV[1]: лимит для пользователя (в секундах)
    -- ARGV[2]: лимит для чата (в секундах)
    -- ARGV[3]: общий лимит (в секундах)

    local user_key = KEYS[1]
    local chat_key = KEYS[2]
    local user_limit = tonumber(ARGV[1])
    local chat_limit = tonumber(ARGV[2])
    local global_limit = tonumber(ARGV[3])

    -- Проверяем лимит для пользователя
    if redis.call('SET', user_key, 1, 'EX', user_limit, 'NX') == nil then
        return 1
    end

    -- Проверяем лимит для чата
    if redis.call('SET', chat_key, 1, 'EX', chat_limit, 'NX') == nil then
        return 1
    end
    
    -- Устанавливаем общий лимит (если он отличается)
    if global_limit ~= user_limit and global_limit ~= chat_limit then
        redis.call('EXPIRE', user_key, global_limit)
        redis.call('EXPIRE', chat_key, global_limit)
    end

    return 0
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
