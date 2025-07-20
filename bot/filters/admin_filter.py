from aiogram.filters import BaseFilter
from aiogram.types import Message

# Импортируем наш сервис для работы с пользователями, который будет передан через DI
from bot.services.user_service import UserService

class IsAdminFilter(BaseFilter):
    """
    Фильтр для проверки, является ли пользователь администратором чата.
    Использует UserService для получения актуальной информации о статусе пользователя.
    """
    async def __call__(self, message: Message, user_service: UserService) -> bool:
        """
        Вызывается aiogram для проверки каждого сообщения, к которому применен фильтр.

        :param message: Объект сообщения от aiogram.
        :param user_service: Экземпляр UserService, автоматически переданный через DI.
        :return: True, если пользователь является администратором, иначе False.
        """
        # Мы не можем проверять права в личных сообщениях с ботом
        if message.chat.type == 'private':
            return False

        user_id = message.from_user.id
        chat_id = message.chat.id

        # Получаем полный профиль пользователя, включая его актуальный статус администратора.
        # UserService сам сделает запрос к Telegram API, что является самым надежным источником.
        user_profile = await user_service.get_or_create_user(user_id, chat_id)

        # Фильтр сработает (вернет True), если у пользователя есть флаг is_admin.
        # Этот флаг устанавливается в user_service на основе актуальных данных от Telegram.
        return user_profile.is_admin

