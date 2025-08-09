# =================================================================================
# Файл: bot/filters/access_filters.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025 - ФИНАЛЬНАЯ ВЕРСИЯ)
# Описание: Динамический фильтр для проверки прав доступа, полностью
#           интегрированный с DI-контейнером.
# ИСПРАВЛЕНИЕ: Сигнатура __call__ приведена в полное соответствие с DI-контейнером Deps.
# =================================================================================

import logging
from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

# ИСПРАВЛЕНО: Импортируем контейнер зависимостей Deps
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
    # Вместо отдельных сервисов (user_service, settings), фильтр теперь принимает
    # единый контейнер 'deps', как его предоставляет aiogram из `dp.start_polling`.
    async def __call__(self, event: Union[Message, CallbackQuery], deps: Deps) -> bool:
    # =========================================================================
        """
        Проверяет роль пользователя. Возвращает True, если у пользователя
        достаточно прав, иначе False.
        """
        user_id = event.from_user.id
        
        # 1. Супер-администраторы из конфига всегда имеют высший приоритет.
        # ИСПРАВЛЕНО: Доступ к настройкам и сервисам осуществляется через объект deps.
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