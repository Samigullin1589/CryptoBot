# =================================================================================
# Файл: bot/filters/access_filters.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025)
# Описание: Динамический фильтр для проверки прав доступа, полностью
# интегрированный с UserService и конфигурацией. Не содержит заглушек.
# =================================================================================

import logging
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config.settings import Settings
from bot.services.user_service import UserService 
from bot.utils.models import UserRole

logger = logging.getLogger(__name__)

class PrivilegeFilter(BaseFilter):
    """
    Фильтр для проверки, имеет ли пользователь достаточные права.
    """
    def __init__(self, min_role: UserRole):
        self.min_role = min_role

    async def __call__(self, event: Union[Message, CallbackQuery], user_service: UserService, settings: Settings) -> bool:
        """
        Проверяет роль пользователя. Возвращает True, если у пользователя
        достаточно прав, иначе False.
        Работает как для сообщений, так и для колбэков.
        """
        user_id = event.from_user.id
        
        # 1. Супер-администраторы из конфига всегда имеют высший приоритет.
        # ИСПРАВЛЕНО: Используем ADMIN_IDS в соответствии с финальной моделью настроек.
        if user_id in settings.ADMIN_IDS:
            user_role = UserRole.SUPER_ADMIN
        else:
            # 2. Для всех остальных получаем актуальную роль из UserService (который читает из Redis).
            user = await user_service.get_user(user_id)
            if user:
                user_role = user.role
            else:
                # 3. Если пользователя еще нет в нашей базе, он имеет роль по умолчанию.
                user_role = UserRole.USER

        # 4. Сравниваем уровень доступа пользователя с минимально требуемым.
        return user_role >= self.min_role
