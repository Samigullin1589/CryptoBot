# ===============================================================
# Файл: bot/middlewares/throttling_middleware.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Middleware для защиты от флуда, использующий атомарный
# Lua-скрипт в Redis для максимальной производительности.
# ===============================================================
import logging
from typing import Callable, Dict, Any, Awaitable

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config.settings import ThrottlingConfig
from bot.services.user_service import UserService, UserProfile
from bot.utils.models import UserRole

logger = logging.getLogger(__name__)

# --- УЛУЧШЕНИЕ: Атомарный Lua-скрипт для проверки троттлинга ---
# Этот скрипт выполняется на стороне Redis как единая, сверхбыстрая операция.
THROTTLE_LUA_SCRIPT = """
-- ARGV[1]: rate_limit (время в секундах для блокировки)
-- KEYS[1]: throttle_key (ключ, который блокируется)
-- KEYS[2]: notified_key (ключ для отметки об уведомлении)

-- Проверяем, заблокирован ли основной ключ
if redis.call('GET', KEYS[1]) then
    -- Пользователь заблокирован. Проверяем, был ли он уже уведомлен.
    if redis.call('GET', KEYS[2]) then
        -- Уже уведомлен, просто возвращаем "2"
        return 2
    else
        -- Еще не уведомлен. Устанавливаем ключ уведомления.
        local ttl = redis.call('TTL', KEYS[1])
        redis.call('SET', KEYS[2], '1', 'EX', ttl)
        -- Возвращаем "1" (заблокирован, но нужно уведомить) и TTL
        return {1, ttl}
    end
end

-- Пользователь не заблокирован. Устанавливаем основной ключ и возвращаем "0".
redis.call('SET', KEYS[1], '1', 'EX', tonumber(ARGV[1]))
return 0
"""

class ThrottlingMiddleware(BaseMiddleware):
    """Интеллектуальный Middleware для защиты от флуда (троттлинга)."""
    
    def __init__(self, redis_client: redis.Redis, user_service: UserService, config: ThrottlingConfig):
        # --- УЛУЧШЕНИЕ: Зависимости и конфиг передаются через конструктор ---
        self.redis = redis_client
        self.user_service = user_service
        self.config = config
        # Кэшируем скрипт в Redis при старте для максимальной производительности
        self.script_sha = None

    async def _register_script(self):
        """Регистрирует Lua-скрипт в Redis и сохраняет его SHA-хэш."""
        if self.script_sha is None:
            self.script_sha = await self.redis.script_load(THROTTLE_LUA_SCRIPT)

    def _get_rate_limit(self, user_profile: UserProfile) -> float:
        """Определяет лимит для пользователя на основе его профиля."""
        if user_profile.role >= UserRole.ADMIN:
            return 0.0

        if user_profile.trust_score >= self.config.trust_score_high_threshold:
            return self.config.rate_limit_high_trust
        if user_profile.trust_score <= self.config.trust_score_low_threshold:
            return self.config.rate_limit_low_trust
        
        return self.config.rate_limit_normal

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        # --- УЛУЧШЕНИЕ: Регистрируем скрипт при первом вызове ---
        if self.script_sha is None:
            await self._register_script()

        user_id = event.from_user.id
        # --- УЛУЧШЕНИЕ: Получаем профиль ОДИН РАЗ и передаем его дальше ---
        user_profile = await self.user_service.get_or_create_user(user_id, event.chat.id)
        data['user_profile'] = user_profile

        rate_limit = self._get_rate_limit(user_profile)
        if rate_limit == 0.0:
            return await handler(event, data)

        # --- УЛУЧШЕНИЕ: Выполняем один атомарный вызов в Redis ---
        throttle_key = f"throttle:{user_id}"
        notified_key = f"throttle_notified:{user_id}"
        
        try:
            result = await self.redis.evalsha(
                self.script_sha, 2, throttle_key, notified_key, str(rate_limit)
            )
        except redis.exceptions.NoScriptError:
            # Если скрипт был вымыт из кэша Redis (например, после SCRIPT FLUSH)
            await self._register_script()
            result = await self.redis.evalsha(
                self.script_sha, 2, throttle_key, notified_key, str(rate_limit)
            )

        if result == 0:  # 0: Все в порядке, пользователь не заблокирован
            return await handler(event, data)
        
        if isinstance(result, list) and result[0] == 1:  # 1: Заблокирован, нужно уведомить
            ttl = result[1]
            await event.answer(f"⏳ Сообщения слишком часто. Попробуйте снова через {ttl} сек.")
        
        # Для result == 2 (Заблокирован и уже уведомлен) мы просто ничего не делаем.
        # В любом случае, кроме result == 0, мы прерываем обработку.
        return