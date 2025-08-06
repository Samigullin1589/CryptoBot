# =================================================================================
# Файл: bot/services/user_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для управления профилями пользователей.
# ИСПРАВЛЕНИЕ: Конструктор __init__ приведен в полное соответствие
# с DI-контейнером (dependencies.py).
# =================================================================================
import logging
from typing import Optional

import redis.asyncio as redis
from aiogram.types import User

from bot.utils.models import UserProfile
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователей в Redis."""
    
    # ИСПРАВЛЕНО: Конструктор теперь принимает 'redis' и не требует 'settings'.
    def __init__(self, redis: redis.Redis):
        """
        Инициализирует сервис.

        :param redis: Асинхронный клиент Redis.
        """
        self.redis = redis
        self.keys = KeyFactory

    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """
        Получает профиль пользователя из Redis по его ID.

        :param user_id: ID пользователя Telegram.
        :return: Объект UserProfile или None, если пользователь не найден.
        """
        profile_key = self.keys.user_profile(user_id)
        user_data = await self.redis.hgetall(profile_key)
        
        if not user_data:
            return None
        
        # Pydantic автоматически обработает нужные поля из словаря
        return UserProfile(**user_data)

    async def create_or_update_user(self, user: User) -> UserProfile:
        """
        Создает или обновляет профиль пользователя в Redis.
        Использует объект User из aiogram для получения всех данных.

        :param user: Объект aiogram.types.User.
        :return: Созданный или обновленный профиль UserProfile.
        """
        profile_key = self.keys.user_profile(user.id)
        
        user_data_to_save = {
            "user_id": user.id,
            "username": user.username or "N/A",
            "full_name": user.full_name,
            "language_code": user.language_code or "N/A",
        }
        
        # Используем hmset для атомарной записи всех полей
        await self.redis.hset(profile_key, mapping=user_data_to_save)
        
        logger.info(f"Профиль для пользователя {user.id} ({user.full_name}) создан/обновлен.")
        
        return UserProfile(**user_data_to_save)

    async def get_or_create_user(self, user: User) -> UserProfile:
        """
        Удобный метод, который получает профиль пользователя,
        а если его нет - создает и возвращает.

        :param user: Объект aiogram.types.User.
        :return: Актуальный профиль пользователя UserProfile.
        """
        profile = await self.get_user_profile(user.id)
        if profile:
            return profile
        return await self.create_or_update_user(user)

