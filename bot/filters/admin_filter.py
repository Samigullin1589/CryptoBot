# ===============================================================
# Файл: bot/filters/admin_filter.py (ОКОНЧАТЕЛЬНЫЙ FIX)
# Описание: Исправлено имя атрибута на 'global_admins' для
# соответствия с UserService и устранения AttributeError.
# ===============================================================
from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.services.user_service import UserService

class IsAdminFilter(BaseFilter):
    """
    Универсальный "альфа" фильтр для проверки прав глобального администратора бота.
    """
    async def __call__(
        self,
        event: Union[Message, CallbackQuery], 
        user_service: UserService
    ) -> bool:
        """
        Вызывается aiogram для проверки каждого события.

        :param event: Событие от Telegram (Message или CallbackQuery).
        :param user_service: Экземпляр UserService, переданный через DI.
        :return: True, если ID пользователя есть в списке глобальных админов.
        """
        user = event.from_user
        if not user:
            return False

        # --- ИСПРАВЛЕНО: Обращаемся к правильному атрибуту 'global_admins' ---
        return user.id in user_service.global_admins
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
