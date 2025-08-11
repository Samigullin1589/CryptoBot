# =================================================================================
# Файл: bot/utils/user_helpers.py (НОВЫЙ ФАЙЛ)
# Описание: Вспомогательные функции для работы с пользователями.
# =================================================================================
import logging
from typing import Optional

from aiogram.types import Message

from bot.services.user_service import UserService
from bot.utils.models import User

logger = logging.getLogger(__name__)

async def extract_target_user(message: Message, user_service: UserService) -> Optional[User]:
    """
    Извлекает целевого пользователя из сообщения.
    Поддерживает три сценария:
    1. Ответ на сообщение (reply).
    2. Упоминание через @username или по user_id.
    3. Сам автор сообщения (если другие сценарии не сработали).
    """
    # Сценарий 1: Ответ на сообщение
    if message.reply_to_message and message.reply_to_message.from_user:
        return await user_service.get_user(message.reply_to_message.from_user.id)

    # Сценарий 2: Упоминание или ID в тексте команды
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        target_arg = args[1]
        
        # Поиск по User ID
        if target_arg.isdigit():
            return await user_service.get_user(int(target_arg))
        
        # Поиск по @username
        if target_arg.startswith('@'):
            # В aiogram нет прямого способа найти ID по username,
            # поэтому этот сценарий будет работать, если бот "видел"
            # пользователя ранее и сохранил его username.
            # Для надежности лучше использовать ID или reply.
            logger.warning("Поиск по @username не является надежным методом.")

    # Если ничего не найдено, возвращаем None
    return None