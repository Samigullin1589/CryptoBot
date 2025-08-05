# bot/filters/access_filters.py
# =================================================================================
# Файл: bot/filters/access_filters.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Фильтры для проверки прав доступа пользователей.
# ИСПРАВЛЕНИЕ: Конструктор PrivilegeFilter теперь корректно обрабатывает
# как строки, так и объекты UserRole, решая ошибку AttributeError.
# =================================================================================

import logging
from enum import Enum, auto
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config.settings import settings
from bot.services.user_service import UserService

logger = logging.getLogger(__name__)

# Определяем иерархию ролей. Используем IntEnum для возможности сравнения.
class UserRole(int, Enum):
    """Определяет роли пользователей с иерархией."""
    USER = 1
    MODERATOR = 2
    ADMIN = 3

class PrivilegeFilter(BaseFilter):
    """
    Фильтр для проверки, имеет ли пользователь достаточные права.
    """
    def __init__(self, min_role: Union[str, UserRole]):
        # ИСПРАВЛЕНИЕ: Делаем конструктор более гибким.
        if isinstance(min_role, UserRole):
            self.min_role = min_role
        elif isinstance(min_role, str):
            try:
                # Преобразуем строку в соответствующий член Enum
                self.min_role = UserRole[min_role.upper()]
            except KeyError:
                logger.error(f"Попытка создать фильтр с неверной ролью: {min_role}")
                raise ValueError(f"Несуществующая роль: {min_role}")
        else:
            raise TypeError(f"min_role должен быть строкой или UserRole, а не {type(min_role)}")

    async def __call__(self, message: Message, user_service: UserService) -> bool:
        """
        Проверяет роль пользователя. Возвращает True, если у пользователя
        достаточно прав, иначе False.
        """
        user_id = message.from_user.id
        
        # Администраторы, указанные в конфиге, всегда имеют высший приоритет
        if user_id in settings.ADMIN_USER_IDS:
            return True

        # Для остальных пользователей получаем роль из сервиса
        user_role_str = await user_service.get_user_role(user_id)
        try:
            user_role = UserRole[user_role_str.upper()]
        except (KeyError, AttributeError):
            user_role = UserRole.USER # Роль по умолчанию, если не найдена

        # Сравниваем уровень доступа пользователя с минимально требуемым
        return user_role.value >= self.min_role.value

