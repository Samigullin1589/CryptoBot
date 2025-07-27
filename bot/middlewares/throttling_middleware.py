# ===============================================================
# Файл: bot/middlewares/throttling_middleware.py (ПРОДАКШН-ВЕРСЯ 2025)
# Описание: Усовершенствованный middleware для защиты от флуда.
# Использует динамические лимиты на основе ролей и рейтинга
# доверия, а также "умные" уведомления для улучшения UX.
# ===============================================================
import logging
from typing import Callable, Dict, Any, Awaitable

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.services.user_service import UserService, UserProfile
from bot.filters.access_filters import UserRole

logger = logging.getLogger(__name__)

# ПРИМЕЧАНИЕ: Этот класс настроек должен быть частью вашего
# основного файла settings.py для централизованного управления.
class ThrottlingSettings:
    """Настройки для middleware троттлинга."""
    # Уровни рейтинга доверия для применения разных лимитов
    TRUST_SCORE_HIGH_THRESHOLD: int = 150
    TRUST_SCORE_LOW_THRESHOLD: int = 50
    
    # Лимиты (минимальный интервал между сообщениями в секундах)
    RATE_LIMIT_HIGH_TRUST: float = 0.5  # Для пользователей с высоким доверием
    RATE_LIMIT_NORMAL: float = 1.0      # Стандартный лимит
    RATE_LIMIT_LOW_TRUST: float = 2.5   # Для пользователей с низким доверием

class ThrottlingMiddleware(BaseMiddleware):
    """
    Интеллектуальный Middleware для защиты от флуда (троттлинга).
    """
    def __init__(self, redis_client: redis.Redis, user_service: UserService):
        self.redis = redis_client
        self.user_service = user_service
        self.settings = ThrottlingSettings()

    def _get_rate_limit(self, user_profile: UserProfile) -> float:
        """Определяет лимит для пользователя на основе его профиля."""
        if user_profile.role >= UserRole.ADMIN:
            return 0.0 # Нет лимита для администраторов

        if user_profile.trust_score >= self.settings.TRUST_SCORE_HIGH_THRESHOLD:
            return self.settings.RATE_LIMIT_HIGH_TRUST
        if user_profile.trust_score < self.settings.TRUST_SCORE_LOW_THRESHOLD:
            return self.settings.RATE_LIMIT_LOW_TRUST
        
        return self.settings.RATE_LIMIT_NORMAL

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обрабатывает каждое входящее сообщение.
        """
        # Мидлварь работает только с сообщениями от реальных пользователей
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        chat_id = event.chat.id

        # Получаем профиль пользователя
        user_profile = await self.user_service.get_or_create_user(user_id, chat_id)
        
        # Определяем персональный лимит
        rate_limit = self._get_rate_limit(user_profile)
        if rate_limit == 0.0:
            return await handler(event, data) # Пропускаем пользователей с иммунитетом

        # Проверяем, не превышен ли лимит
        throttle_key = f"throttle:{user_id}:{chat_id}"
        is_throttled = await self.redis.get(throttle_key)

        if is_throttled:
            # Если пользователь уже под троттлингом, проверяем, нужно ли его уведомлять
            notified_key = f"throttle_notified:{user_id}:{chat_id}"
            if not await self.redis.get(notified_key):
                # Уведомляем только один раз за период блокировки
                ttl = await self.redis.ttl(throttle_key)
                await event.answer(f"⏳ Сообщения слишком часто. Попробуйте снова через {ttl} сек.")
                await self.redis.set(notified_key, "1", ex=ttl)
            
            # Прекращаем обработку сообщения
            return

        # Если лимит не превышен, устанавливаем ключ троттлинга
        # Время жизни ключа чуть больше лимита для надежности
        await self.redis.set(throttle_key, "1", ex=int(rate_limit) + 1)
        
        # Передаем управление дальше по цепочке
        return await handler(event, data)
