# =================================================================================
# Файл: bot/filters/access_filters.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ - ИСПРАВЛЕННЫЙ)
# Описание: Фильтр прав доступа, адаптированный под механизм DI в aiogram 3+.
# ИСПРАВЛЕНИЕ: UserRole теперь импортируется из bot.utils.models для
#              устранения циклического импорта.
# =================================================================================

import logging
from typing import Any, Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.utils.dependencies import Deps
from bot.utils.models import UserRole # <-- ИСПРАВЛЕНО

logger = logging.getLogger(__name__)

class PrivilegeFilter(BaseFilter):
    """
    Фильтр для проверки, имеет ли пользователь достаточные права.
    """
    def __init__(self, min_role: UserRole):
        self.min_role = min_role

    async def __call__(self, event: Union[Message, CallbackQuery], **data: Any) -> bool:
        """
        Проверяет роль пользователя.
        """
        deps: Deps = data.get('deps')
        
        if not deps:
            logger.error("Критическая ошибка: DI-контейнер 'deps' не был передан в PrivilegeFilter.")
            return False

        user_id = event.from_user.id
        
        if user_id in deps.settings.admin_ids:
            user_role = UserRole.SUPER_ADMIN
        else:
            user = await deps.user_service.get_user(user_id)
            user_role = user.role if user else UserRole.USER

        return user_role >= self.min_role
