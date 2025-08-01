# ===============================================================
# Файл: bot/filters/access_filters.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Фильтр доступа, использующий корректные имена переменных.
# ===============================================================
from enum import IntEnum
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config.settings import settings

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
    def __init__(self, min_role: str):
        self.min_role = UserRole[min_role.upper()]

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id
        
        user_role = UserRole.USER
        # Используем новое, корректно распарсенное свойство
        if user_id in settings.admin_ids_list: # <<< ИСПРАВЛЕНИЕ ЗДЕСЬ
            user_role = UserRole.ADMIN
        
        return user_role >= self.min_role