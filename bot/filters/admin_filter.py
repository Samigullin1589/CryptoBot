from aiogram.filters import Filter
from aiogram.types import Message
from bot.config.settings import settings

class IsAdmin(Filter):
    """
    Кастомный фильтр для проверки, является ли пользователь администратором.
    """
    async def __call__(self, message: Message) -> bool:
        # Сравниваем ID пользователя, отправившего сообщение,
        # с ID администратора из файла настроек.
        return message.from_user.id == settings.admin_chat_id