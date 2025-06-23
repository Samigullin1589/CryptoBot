from aiogram.filters import BaseFilter
from aiogram.types import Message
from bot.config.settings import settings

class SpamFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Игнорируем сообщения от администратора и других доверенных лиц
        if message.from_user.id in settings.ALLOWED_LINK_USER_IDS:
            return False

        # Проверяем на наличие ссылок
        if message.entities:
            for entity in message.entities:
                if entity.type in ["url", "text_link"]:
                    return True # Найдена ссылка, это спам

        # Проверяем на наличие стоп-слов в тексте сообщения
        if message.text:
            text_lower = message.text.lower()
            for word in settings.STOP_WORDS:
                if word in text_lower:
                    return True # Найдено стоп-слово, это спам
        
        # Если ничего не найдено, это не спам
        return False