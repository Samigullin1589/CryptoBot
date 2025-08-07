# =================================================================================
# Файл: bot/services/user_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для управления профилями пользователей.
# ИСПРАВЛЕНИЕ: Добавлен недостающий метод update_user_activity.
# =================================================================================
import logging
from typing import Optional, List
from datetime import datetime, timedelta

import redis.asyncio as redis
from aiogram.types import User

from bot.utils.models import UserProfile
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователей в Redis."""
    
    def __init__(self, redis: redis.Redis):
        self.redis = redis
        self.keys = KeyFactory

    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        profile_key = self.keys.user_profile(user_id)
        user_data = await self.redis.hgetall(profile_key)
        if not user_data:
            return None
        return UserProfile(**{k.decode('utf-8'): v.decode('utf-8') for k, v in user_data.items()})

    async def create_or_update_user(self, user: User) -> UserProfile:
        profile_key = self.keys.user_profile(user.id)
        user_data_to_save = {
            "user_id": user.id,
            "username": user.username or "N/A",
            "full_name": user.full_name,
            "language_code": user.language_code or "N/A",
        }
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(profile_key, mapping=user_data_to_save)
            pipe.sadd(self.keys.all_users_set(), user.id)
            await pipe.execute()
        
        logger.info(f"Профиль для пользователя {user.id} ({user.full_name}) создан/обновлен.")
        return UserProfile(**user_data_to_save)

    async def get_or_create_user(self, user: User) -> UserProfile:
        profile = await self.get_user_profile(user.id)
        if profile:
            return profile
        return await self.create_or_update_user(user)

    async def get_all_user_ids(self) -> List[int]:
        user_ids_raw = await self.redis.smembers(self.keys.all_users_set())
        return [int(user_id) for user_id in user_ids_raw]

    # ИСПРАВЛЕНО: Добавлен недостающий метод
    async def update_user_activity(self, user_id: int, chat_id: int):
        """
        Обновляет временные метки активности пользователя и чата.
        Использует Redis Sets для отслеживания уникальных активных пользователей.
        """
        now = datetime.utcnow()
        today_str = now.strftime('%Y-%m-%d')
        week_str = now.strftime('%Y-%U') # Год и номер недели

        day_key = f"users:active:day:{today_str}"
        week_key = f"users:active:week:{week_str}"

        async with self.redis.pipeline(transaction=True) as pipe:
            # Добавляем пользователя в множество активных за день/неделю
            pipe.sadd(day_key, user_id)
            pipe.sadd(week_key, user_id)
            # Устанавливаем время жизни для ключей, чтобы они автоматически удалялись
            pipe.expire(day_key, timedelta(days=2))
            pipe.expire(week_key, timedelta(weeks=2))
            await pipe.execute()
