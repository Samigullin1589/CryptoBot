import logging
from datetime import datetime
from typing import Callable, Dict, Any, Awaitable
import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)

class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания активности пользователей при каждом входящем сообщении или колбэке.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Пытаемся получить ID пользователя из любого типа апдейта
        user = data.get('event_from_user')
        if not user:
            return await handler(event, data)

        user_id = user.id
        current_timestamp = int(datetime.now().timestamp())

        try:
            # ZADD обновляет "счет" (в нашем случае - время) пользователя, если он уже существует,
            # или добавляет нового, если его нет.
            await self.redis.zadd("stats:user_activity", {str(user_id): current_timestamp})
        except Exception as e:
            logger.error(f"Failed to update user {user_id} activity: {e}")

        # Продолжаем обработку апдейта
        return await handler(event, data)
