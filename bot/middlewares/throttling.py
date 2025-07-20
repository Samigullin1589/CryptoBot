import logging
from typing import Callable, Dict, Any, Awaitable

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Message

# Импортируем наш основной сервис для работы с пользователями
from bot.services.user_service import UserService

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    """
    Интеллектуальный Middleware для защиты от флуда (троттлинга).
    Применяет разные лимиты к пользователям в зависимости от их рейтинга доверия
    и уведомляет их о превышении лимита.
    """
    def __init__(self, redis_client: redis.Redis, user_service: UserService):
        """
        Инициализирует middleware.
        
        :param redis_client: Клиент Redis для хранения временных данных о флуде.
        :param user_service: Сервис для получения данных о репутации пользователя.
        """
        self.redis = redis_client
        self.user_service = user_service

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обрабатывает каждое входящее сообщение.
        """
        # Мидлварь работает только с сообщениями от пользователей
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        chat_id = event.chat.id

        # Получаем профиль пользователя, чтобы узнать его статус и рейтинг доверия
        user_profile = await self.user_service.get_or_create_user(user_id, chat_id)

        # Администраторы и пользователи с иммунитетом не подвергаются троттлингу
        if user_profile.is_admin or user_profile.has_immunity:
            return await handler(event, data)

        # --- Динамическое определение лимита на основе рейтинга доверия ---
        if user_profile.trust_score >= 150:
            rate_limit = 0.5  # Доверенные пользователи могут писать очень часто
        elif user_profile.trust_score >= 50:
            rate_limit = 1.0  # Стандартный лимит для обычных пользователей
        else:
            rate_limit = 2.5  # Строгий лимит для пользователей с низкой репутацией

        # Ключ для хранения времени последнего сообщения в Redis
        throttle_key = f"throttle:{user_id}:{chat_id}"
        
        # Проверяем, было ли уже сообщение от этого пользователя
        is_throttled = await self.redis.get(throttle_key)

        if is_throttled:
            # Если пользователь превысил лимит, уведомляем его и отменяем обработку сообщения
            ttl = await self.redis.ttl(throttle_key)
            await event.answer(f"⏳ Сообщения слишком часто. Попробуйте снова через {ttl} сек.")
            
            # --- ИЗМЕНЕНИЕ: Самый надежный способ отмены ---
            # Просто выходим из мидлвари, не вызывая следующий обработчик.
            # Это остановит обработку события.
            return

        # Если лимит не превышен, устанавливаем ключ с временем жизни, равным лимиту
        await self.redis.set(throttle_key, "1", ex=int(rate_limit) + 1)
        
        # Передаем управление дальше
        return await handler(event, data)
