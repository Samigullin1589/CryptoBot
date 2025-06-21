import time
from typing import Any, Awaitable, Callable, Dict

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Message

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
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        key = f"throttle:{event.from_user.id}"
        last_call = await self.redis.get(key)

        if last_call:
            elapsed_time = time.time() - float(last_call)
            if elapsed_time < self.default_rate_limit:
                return
        
        await self.redis.set(key, time.time(), ex=int(self.default_rate_limit) + 1)
        return await handler(event, data)