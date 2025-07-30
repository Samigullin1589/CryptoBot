# =================================================================================
# Файл: bot/services/user_service.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ИСПРАВЛЕНА)
# =================================================================================
import logging
from typing import Optional

import redis.asyncio as redis
from aiogram import Bot

from bot.config.settings import Settings # <<< ИСПРАВЛЕНО ЗДЕСЬ
from bot.utils.models import UserProfile
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователя."""

    def __init__(self, redis_client: redis.Redis, settings: Settings): # <<< ИСПРАВЛЕНО ЗДЕСЬ
        self.redis = redis_client
        self.settings = settings
        self.keys = KeyFactory

    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Получает профиль пользователя из Redis."""
        user_data = await self.redis.hgetall(self.keys.user_profile(user_id))
        if not user_data:
            return None
        return UserProfile(**user_data)

    async def create_or_update_user(self, user_id: int, username: str, full_name: str, language_code: str) -> UserProfile:
        """Создает или обновляет профиль пользователя."""
        profile_key = self.keys.user_profile(user_id)
        user_data = {
            "user_id": user_id,
            "username": username or "N/A",
            "full_name": full_name,
            "language_code": language_code or "N/A",
        }
        await self.redis.hmset(profile_key, user_data)
        logger.info(f"Профиль для пользователя {user_id} создан/обновлен.")
        return UserProfile(**user_data)

    async def get_or_create_user(self, user_id: int, username: str, full_name: str, language_code: str) -> UserProfile:
        """Удобный метод для получения или создания пользователя за один вызов."""
        profile = await self.get_user_profile(user_id)
        if profile:
            return profile
        return await self.create_or_update_user(user_id, username, full_name, language_code)