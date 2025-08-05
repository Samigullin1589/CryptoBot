# bot/filters/access_filters.py
# =================================================================================
# Файл: bot/filters/access_filters.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Фильтры для проверки прав доступа пользователей.
# ИСПРАВЛЕНИЕ: Добавлена недостающая роль SUPER_ADMIN для решения AttributeError.
# =================================================================================

import logging
from enum import Enum
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config.settings import settings
# Предполагается, что зависимость user_service будет передана в хэндлер
# from bot.services.user_service import UserService 

logger = logging.getLogger(__name__)

# Определяем иерархию ролей. Используем IntEnum для возможности сравнения.
class UserRole(int, Enum):
    """Определяет роли пользователей с иерархией."""
    USER = 1
    MODERATOR = 2
    ADMIN = 3
    SUPER_ADMIN = 4 # ИСПРАВЛЕНО: Добавлена недостающая роль

class PrivilegeFilter(BaseFilter):
    """
    Фильтр для проверки, имеет ли пользователь достаточные права.
    """
    def __init__(self, min_role: Union[str, UserRole]):
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

    async def __call__(self, message: Message) -> bool:
        """
        Проверяет роль пользователя. Возвращает True, если у пользователя
        достаточно прав, иначе False.
        """
        user_id = message.from_user.id
        
        # SUPER_ADMIN - это пользователи из конфига
        if user_id in settings.ADMIN_USER_IDS:
            user_role = UserRole.SUPER_ADMIN
        else:
            # В реальном приложении здесь должна быть логика получения роли из БД
            # Например, через user_service, который нужно будет передать в хэндлер
            # user_role_str = await user_service.get_user_role(user_id)
            # user_role = UserRole[user_role_str.upper()]
            user_role = UserRole.USER # Заглушка для простоты

        # Сравниваем уровень доступа пользователя с минимально требуемым
        return user_role.value >= self.min_role.value

