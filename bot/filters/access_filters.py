# =================================================================================
# Файл: bot/filters/access_filters.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025 - ФИНАЛЬНАЯ ВЕРСИЯ)
# Описание: Фильтр прав доступа, адаптированный под механизм DI в aiogram 3+.
# ИСПРАВЛЕНИЕ: __call__ теперь корректно извлекает контейнер 'deps' из
#              словаря 'data', передаваемого aiogram в фильтры.
# =================================================================================

import logging
from typing import Union, Dict, Any

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

# Импортируем зависимости, которые нам нужно будет найти
from bot.utils.dependencies import Deps
from bot.utils.models import UserRole

logger = logging.getLogger(__name__)

class PrivilegeFilter(BaseFilter):
    """
    Фильтр для проверки, имеет ли пользователь достаточные права.
    """
    def __init__(self, min_role: UserRole):
        self.min_role = min_role

    # ========================== КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ==========================
    # aiogram передает все зависимости в фильтры внутри словаря `data`.
    # Мы принимаем этот словарь и извлекаем из него наш контейнер `deps`.
    async def __call__(self, event: Union[Message, CallbackQuery], **data: Any) -> bool:
    # =========================================================================
        """
        Проверяет роль пользователя. Возвращает True, если у пользователя
        достаточно прав, иначе False.
        """
        # Извлекаем контейнер зависимостей из переданных данных
        deps: Deps = data.get('deps')
        
        # Если по какой-то причине контейнер не был передан, блокируем доступ
        if not deps:
            logger.error("Критическая ошибка: DI-контейнер 'deps' не был передан в PrivilegeFilter.")
            return False

        user_id = event.from_user.id
        
        # 1. Супер-администраторы из конфига всегда имеют высший приоритет.
        if user_id in deps.settings.admin_ids:
            user_role = UserRole.SUPER_ADMIN
        else:
            # 2. Для всех остальных получаем актуальную роль из UserService.
            user = await deps.user_service.get_user(user_id)
            if user:
                user_role = user.role
            else:
                # 3. Если пользователя еще нет в нашей базе, он имеет роль по умолчанию.
                user_role = UserRole.USER

        # 4. Сравниваем уровень доступа пользователя с минимально требуемым.
        return user_role >= self.min_role