import time
from typing import Any, Awaitable, Callable, Dict

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Message

# Это наш middleware-класс для защиты от спама (троттлинга)
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis_client: redis.Redis, default_rate_limit: float = 1.0):
        self.redis = redis_client
        self.default_rate_limit = default_rate_limit

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Мы будем ограничивать только сообщения от реальных пользователей
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        # Ключ для Redis будет уникальным для каждого пользователя
        key = f"throttle:{event.from_user.id}"

        # Проверяем, есть ли запись о последнем запросе пользователя
        last_call = await self.redis.get(key)

        if last_call:
            elapsed_time = time.time() - float(last_call)
            # Если с последнего запроса прошло слишком мало времени, прерываем обработку
            if elapsed_time < self.default_rate_limit:
                # Можно отправить пользователю сообщение, но лучше просто проигнорировать
                # для уменьшения спама в ответ на спам.
                return

        # Если все в порядке, обновляем время последнего запроса и продолжаем
        # Устанавливаем время жизни ключа чуть больше лимита для автоочистки Redis
        await self.redis.set(key, time.time(), ex=int(self.default_rate_limit) + 1)
        return await handler(event, data)