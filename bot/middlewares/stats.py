from typing import Callable, Dict, Any, Awaitable
from datetime import datetime
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import redis.asyncio as redis

class StatsMiddleware(BaseMiddleware):
    """
    Middleware для сбора статистики использования команд и активности пользователей.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        
        # Проверяем, новый ли это пользователь, и если да, сохраняем время первого контакта
        is_new_user = await self.redis.sadd("users:known", user_id)
        if is_new_user:
            await self.redis.zadd("stats:user_first_seen", {str(user_id): int(datetime.now().timestamp())})
        
        # Обновляем время последней активности пользователя
        await self.redis.zadd("stats:user_activity", {str(user_id): int(datetime.now().timestamp())})

        # Считаем использование команд/кнопок
        command_name = ""
        if isinstance(event, Message) and event.text and event.text.startswith('/'):
            command_name = event.text.split()[0]
        elif isinstance(event, CallbackQuery) and event.data:
            command_name = event.data.split('_')[0]

        if command_name:
            await self.redis.zincrby("stats:commands", 1, command_name)

        return await handler(event, data)