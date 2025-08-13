# =================================================================================
# Файл: bot/keyboards/news_keyboards.py (ДИНАМИЧЕСКИЙ, АВГУСТ 2025)
# Описание: Клавиатуры для раздела новостей, которые строятся
# на основе данных, полученных из конфигурации.
# ИСПРАВЛЕНИЕ: Добавлен метод .pack() для корректной сериализации callback-данных.
# =================================================================================
from typing import Dict
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from .callback_factories import NewsCallback, MenuCallback

def get_news_sources_keyboard(sources: Dict[str, str]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора источника новостей на основе
    динамически загруженного словаря источников.
    
    :param sources: Словарь, где ключ - 'source_key', значение - 'Source Name'.
    """
    builder = InlineKeyboardBuilder()

    if not sources:
        # Если по какой-то причине источники не загрузились, показываем информационное сообщение
        builder.button(
            text="Нет доступных источников новостей",
            callback_data="do_nothing" # Некликабельная кнопка
        )
    else:
        for key, name in sources.items():
            builder.button(
                text=f"📰 {name}",
                callback_data=NewsCallback(action="get_feed", source_key=key).pack() # ИСПРАВЛЕНО
            )
    
    builder.button(
        text="⬅️ Назад в главное меню",
        callback_data=MenuCallback(level=0, action="main").pack() # ИСПРАВЛЕНО
    )

    builder.adjust(1) # Каждая кнопка на новой строке
    return builder.as_markup()