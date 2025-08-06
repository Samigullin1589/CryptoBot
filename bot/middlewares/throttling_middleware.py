# =================================================================================
# Файл: bot/middlewares/throttling_middleware.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Middleware для защиты от флуда, адаптированный для aiogram 3+.
# ИСПРАВЛЕНИЕ: Логика полностью переписана для корректной работы
# с объектом Update и извлечения пользователя/чата из data.
# =================================================================================
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update, User

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

    if redis.call('SET', user_key, 1, 'EX', user_limit, 'NX') == nil then
        return 1
    end

    if redis.call('SET', chat_key, 1, 'EX', chat_limit, 'NX') == nil then
        return 1
    end
    
    if global_limit ~= user_limit and global_limit ~= chat_limit then
        redis.call('EXPIRE', user_key, global_limit)
        redis.call('EXPIRE', chat_key, global_limit)
    end

    return 0
"""

class ThrottlingMiddleware(BaseMiddleware):
    """
    Универсальный middleware для защиты от флуда, работающий с любыми типами Update.
    """
    def __init__(self, storage: RedisStorage):
        self.storage = storage
        self.rate_limit = settings.throttling.rate_limit
        self.user_rate_limit = settings.throttling.user_rate_limit
        self.chat_rate_limit = settings.throttling.chat_rate_limit
        self.script_sha: Optional[str] = None

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # ИСПРАВЛЕНО: Правильный способ получить пользователя и чат в aiogram 3+
        user: Optional[User] = data.get("event_from_user")
        chat = data.get("event_chat")

        # Если в событии нет пользователя (например, системное обновление), пропускаем
        if not user:
            return await handler(event, data)

        # Если нет чата (например, inline-запрос), используем ID пользователя как ID чата
        chat_id = chat.id if chat else user.id

        if self.script_sha is None:
            self.script_sha = await self.storage.redis.script_load(THROTTLE_LUA_SCRIPT)

        is_throttled = await self.storage.redis.evalsha(
            self.script_sha,
            2,
            f"throttle_user:{user.id}",
            f"throttle_chat:{chat_id}",
            self.user_rate_limit,
            self.chat_rate_limit,
            self.rate_limit
        )

        if is_throttled:
            return

        return await handler(event, data)
