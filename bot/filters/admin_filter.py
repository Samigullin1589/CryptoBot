# ===============================================================
# Файл: bot/filters/admin_filter.py (ОКОНЧАТЕЛЬНЫЙ FIX)
# Описание: "Альфа" версия фильтра администратора. Работает во
# всех типах чатов и делает одну быструю проверку по ID.
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
        # 1. Получаем объект пользователя. Он есть и в Message, и в CallbackQuery.
        user = event.from_user
        if not user:
            return False # Если пользователя нет, это точно не админ

        # 2. Проверяем ID пользователя по списку админов, который хранится в user_service.
        # Этот список загружается из твоих настроек при старте бота.
        # Это единственная и самая надежная проверка, которая нужна.
        return user.id in user_service.admin_user_ids
