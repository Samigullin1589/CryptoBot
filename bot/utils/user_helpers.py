# =================================================================================
# Файл: bot/utils/user_helpers.py (НОВЫЙ ФАЙЛ)
# Описание: Вспомогательные функции для работы с пользователями.
# ИСПРАВЛЕНИЕ: Добавлена логика поиска пользователя по @username.
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
    Поддерживает сценарии: ответ (reply), упоминание (@username) или ID.
    """
    # Сценарий 1: Ответ на сообщение
    if message.reply_to_message and message.reply_to_message.from_user:
        return await user_service.get_user(message.reply_to_message.from_user.id)

    # Сценарий 2: Упоминание или ID в тексте команды
    args = message.text.split()
    if len(args) > 1:
        target_arg = args[1]
        
        # Поиск по User ID
        if target_arg.isdigit():
            return await user_service.get_user(int(target_arg))
        
        # ИСПРАВЛЕНО: Поиск по @username теперь работает
        if target_arg.startswith('@'):
            return await user_service.get_user_by_username(target_arg)

    # Если ничего не найдено, возвращаем None
    return None