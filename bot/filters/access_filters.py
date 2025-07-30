# ===============================================================
# Файл: bot/filters/access_filters.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# ===============================================================
from enum import IntEnum
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config.settings import settings # Импортируем исправленные настройки

class UserRole(IntEnum):
    """Перечисление ролей с иерархией."""
    USER = 0
    MODERATOR = 1
    ADMIN = 2
    SUPER_ADMIN = 3

class PrivilegeFilter(BaseFilter):
    """
    Фильтр, который проверяет, имеет ли пользователь достаточный уровень привилегий.
    """
    def __init__(self, min_role: UserRole):
        self.min_role = min_role

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id
        
        user_role = UserRole.USER
        # Используем исправленные пути к настройкам
        if user_id in settings.ADMIN_IDS: # Пример, возможно у вас SUPER_ADMIN_IDS
            user_role = UserRole.ADMIN
        
        return user_role >= self.min_role