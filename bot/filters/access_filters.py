# =================================================================================
# Файл: bot/filters/access_filters.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025 - ИСПРАВЛЕННЫЙ)
# Описание: Динамический фильтр для проверки прав доступа.
# ИСПРАВЛЕНИЕ: Сигнатура __call__ приведена в соответствие с DI-контейнером Deps.
# =================================================================================

import logging
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

# ИСПРАВЛЕНО: Импортируем контейнер зависимостей
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
    # Вместо отдельных сервисов принимаем единый контейнер 'deps',
    # как его предоставляет aiogram из start_polling.
    async def __call__(self, event: Union[Message, CallbackQuery], deps: Deps) -> bool:
    # =========================================================================
        """
        Проверяет роль пользователя. Возвращает True, если у пользователя
        достаточно прав, иначе False.
        Работает как для сообщений, так и для колбэков.
        """
        user_id = event.from_user.id
        
        # 1. Супер-администраторы из конфига всегда имеют высший приоритет.
        # ИСПРАВЛЕНО: Получаем доступ к настройкам через deps.settings
        if user_id in deps.settings.admin_ids:
            user_role = UserRole.SUPER_ADMIN
        else:
            # 2. Для всех остальных получаем актуальную роль из UserService
            # ИСПРАВЛЕНО: Получаем доступ к сервису через deps.user_service
            user = await deps.user_service.get_user(user_id)
            if user:
                user_role = user.role
            else:
                # 3. Если пользователя еще нет в нашей базе, он имеет роль по умолчанию.
                user_role = UserRole.USER

        # 4. Сравниваем уровень доступа пользователя с минимально требуемым.
        return user_role >= self.min_role