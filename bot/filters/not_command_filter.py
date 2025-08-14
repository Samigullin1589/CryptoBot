from aiogram.filters import BaseFilter
from aiogram.types import Message
from aiogram.enums import MessageEntityType


class NotCommandFilter(BaseFilter):
    """
    Возвращает True только для сообщений, которые НЕ являются командами бота.
    Учитывает как префикс '/', так и наличие entity типа BOT_COMMAND.
    """

    async def __call__(self, message: Message) -> bool:
        text = (message.text or "").strip()
        if text.startswith("/"):
            return False

        try:
            for ent in (message.entities or []):
                # Команда обычно идёт в начале сообщения
                if ent.type == MessageEntityType.BOT_COMMAND and ent.offset == 0:
                    return False
        except Exception:
            # Если entities нет или формат неожиданный — считаем, что это не команда.
            pass
        return True
