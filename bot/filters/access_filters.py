# ===============================================================
# Файл: bot/filters/access_filters.py (НОВЫЙ ФАЙЛ)
# Описание: Фильтры для гранулярного контроля доступа к хэндлерам.
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
    def __init__(self, min_role: UserRole):
        self.min_role = min_role

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id
        
        user_role = UserRole.USER
        if user_id in settings.admin.super_admin_ids:
            user_role = UserRole.SUPER_ADMIN
        elif user_id in settings.admin.admin_ids:
            user_role = UserRole.ADMIN
        elif user_id in settings.admin.moderator_ids:
            user_role = UserRole.MODERATOR
            
        return user_role >= self.min_role