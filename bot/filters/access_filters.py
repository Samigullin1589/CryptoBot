# ===============================================================
# Файл: bot/filters/access_filters.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Внедрена система управления доступом на основе ролей (RBAC).
# Заменяет простую проверку админа на гибкую иерархию ролей и
# предоставляет мощные фильтры для использования в хэндлерах.
# ===============================================================

from enum import IntEnum
from typing import Union, List

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.services.user_service import UserService

class UserRole(IntEnum):
    """
    Определяет иерархию ролей пользователей в системе.
    Использование IntEnum позволяет легко сравнивать уровни доступа
    (например, UserRole.ADMIN >= UserRole.MODERATOR).
    """
    BANNED = -1      # Заблокированный пользователь
    GUEST = 0        # Незарегистрированный пользователь (потенциально)
    USER = 1         # Стандартный, зарегистрированный пользователь
    MODERATOR = 2    # Модератор с расширенными правами
    ADMIN = 3        # Администратор с полным доступом к большинству функций
    SUPER_ADMIN = 4  # Владелец бота с абсолютными правами

class RoleFilter(BaseFilter):
    """
    Фильтр для проверки, входит ли роль пользователя в заданный список ролей.
    
    Пример использования:
    @router.message(Command("moderate"), RoleFilter([UserRole.MODERATOR, UserRole.ADMIN]))
    async def moderate_handler(message: Message):
        ...
    """
    def __init__(self, allowed_roles: List[UserRole]):
        """
        :param allowed_roles: Список ролей, которым разрешен доступ.
        """
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        user_service: UserService
    ) -> bool:
        """
        Проверяет, соответствует ли роль пользователя требуемым.

        :param event: Событие от Telegram (Message или CallbackQuery).
        :param user_service: Сервис для работы с данными пользователя (DI).
        :return: True, если роль пользователя находится в списке разрешенных.
        """
        user = event.from_user
        if not user:
            return False

        # Предполагается, что user_service может получить роль по ID
        # Это более надежно, чем доверять данным из сессии, которые могут устареть.
        user_role = await user_service.get_user_role(user.id)
        
        return user_role in self.allowed_roles

class PrivilegeFilter(BaseFilter):
    """
    Фильтр для проверки, что уровень привилегий пользователя не ниже заданного.
    Это основной и наиболее часто используемый фильтр для разграничения доступа.

    Пример использования (замена старого IsAdminFilter):
    @router.message(Command("admin_panel"), PrivilegeFilter(min_role=UserRole.ADMIN))
    async def admin_panel_handler(message: Message):
        ...
    """
    def __init__(self, min_role: UserRole):
        """
        :param min_role: Минимальная роль, необходимая для доступа.
        """
        self.min_role = min_role

    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        user_service: UserService
    ) -> bool:
        """
        Проверяет, достаточен ли уровень привилегий пользователя.

        :param event: Событие от Telegram (Message или CallbackQuery).
        :param user_service: Сервис для работы с данными пользователя (DI).
        :return: True, если роль пользователя больше или равна минимально требуемой.
        """
        user = event.from_user
        if not user:
            return False

        user_role = await user_service.get_user_role(user.id)

        # Сравнение возможно благодаря использованию IntEnum
        return user_role >= self.min_role

# --- Для обратной совместимости и удобства ---
# Старый IsAdminFilter теперь является частным случаем PrivilegeFilter.
# Вы можете использовать его так для ясности в коде, отвечающем за админ-команды.
IsAdminFilter = PrivilegeFilter(min_role=UserRole.ADMIN)
IsSuperAdminFilter = PrivilegeFilter(min_role=UserRole.SUPER_ADMIN)
