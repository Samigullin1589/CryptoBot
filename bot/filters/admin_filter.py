from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

# Импортируем наш сервис для работы с пользователями
from bot.services.user_service import UserService

class IsAdminFilter(BaseFilter):
    """
    Универсальный "альфа" фильтр для проверки прав администратора.
    Корректно работает как с сообщениями (Message), так и с нажатиями на кнопки (CallbackQuery).
    """
    async def __call__(
        self,
        event: Union[Message, CallbackQuery], 
        user_service: UserService
    ) -> bool:
        """
        Вызывается aiogram для проверки каждого события, к которому применен фильтр.

        :param event: Событие от Telegram (может быть Message или CallbackQuery).
        :param user_service: Экземпляр UserService, автоматически переданный через DI.
        :return: True, если пользователь является администратором, иначе False.
        """
        # 1. Получаем объект пользователя. Он есть и в Message, и в CallbackQuery.
        user = event.from_user
        if not user:
            return False # Если пользователя нет, это не админ

        # 2. Определяем, откуда брать информацию о чате, в зависимости от типа события.
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            # У CallbackQuery информация о чате находится внутри оригинального сообщения
            if not event.message:
                return False # На всякий случай, если у колбэка нет сообщения
            chat = event.message.chat
        else:
            # Если придет какой-то неизвестный тип события, отклоняем
            return False

        # 3. В личных чатах нет администраторов, поэтому сразу отклоняем
        if chat.type == 'private':
            return False

        # 4. Используем наш UserService для получения актуального статуса пользователя
        user_profile = await user_service.get_or_create_user(user.id, chat.id)

        # 5. Возвращаем результат проверки
        return user_profile.is_admin
