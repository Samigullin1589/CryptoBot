from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from bot.config.settings import settings
from typing import Union

class IsAdmin(Filter):
    """
    Кастомный фильтр для проверки, является ли пользователь администратором.
    Срабатывает и на сообщения, и на нажатия кнопок.
    """
    async def __call__(self, update: Union[Message, CallbackQuery]) -> bool:
        return update.from_user.id == settings.admin_chat_id