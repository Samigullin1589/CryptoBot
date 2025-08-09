# =================================================================================
# Файл: bot/middlewares/throttling_middleware.py (ВЕРСЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Middleware для защиты от флуда, адаптированный для aiogram 3+.
# ИСПРАВЛЕНИЕ: LUA-скрипт переведен на миллисекунды (PEX) для поддержки
# дробных значений rate_limit.
# =================================================================================
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update, User

# ИЗМЕНЕНО: Импортируем экземпляр настроек из нового файла
from bot.config.config import settings

# ИСПРАВЛЕНО: LUA-скрипт теперь использует PEX для работы с миллисекундами
THROTTLE_LUA_SCRIPT = """
    -- KEYS[1]: ключ для пользователя
    -- KEYS[2]: ключ для чата
    -- ARGV[1]: лимит для пользователя (в миллисекундах)
    -- ARGV[2]: лимит для чата (в миллисекундах)

    local user_key = KEYS[1]
    local chat_key = KEYS[2]
    local user_limit_ms = tonumber(ARGV[1])
    local chat_limit_ms = tonumber(ARGV[2])

    if redis.call('SET', user_key, 1, 'PX', user_limit_ms, 'NX') == nil then
        return 1
    end

    if redis.call('SET', chat_key, 1, 'PX', chat_limit_ms, 'NX') == nil then
        return 1
    end

    return 0
"""

class ThrottlingMiddleware(BaseMiddleware):
    """
    Универсальный middleware для защиты от флуда, работающий с любыми типами Update.
    """
    def __init__(self, storage: RedisStorage):
        self.storage = storage
        # Переводим лимиты из секунд в миллисекунды при инициализации
        self.user_rate_limit_ms = int(settings.throttling.user_rate_limit * 1000)
        self.chat_rate_limit_ms = int(settings.throttling.chat_rate_limit * 1000)
        self.script_sha: Optional[str] = None

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user: Optional[User] = data.get("event_from_user")
        chat = data.get("event_chat")

        if not user:
            return await handler(event, data)

        chat_id = chat.id if chat else user.id

        if self.script_sha is None:
            self.script_sha = await self.storage.redis.script_load(THROTTLE_LUA_SCRIPT)

        # ИСПРАВЛЕНО: Передаем лимиты в миллисекундах
        is_throttled = await self.storage.redis.evalsha(
            self.script_sha,
            2,
            f"throttle_user:{user.id}",
            f"throttle_chat:{chat_id}",
            self.user_rate_limit_ms,
            self.chat_rate_limit_ms
        )

        if is_throttled:
            return

        return await handler(event, data)