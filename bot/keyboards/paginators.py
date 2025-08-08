# =================================================================================
# Файл: bot/keyboards/paginators.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Универсальная фабрика для создания клавиатур с пагинацией.
# =================================================================================

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def create_paginator_keyboard(
    page: int, 
    total_pages: int, 
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для пагинации.

    :param page: Текущая страница (начиная с 0).
    :param total_pages: Общее количество страниц.
    :param callback_prefix: Префикс для callback_data (например, 'asics_page').
    :return: Готовая инлайн-клавиатура.
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка "назад"
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"{callback_prefix}:{page - 1}")
    
    # Кнопка "вперед"
    if page < total_pages - 1:
        builder.button(text="Вперед ➡️", callback_data=f"{callback_prefix}:{page + 1}")
        
    # Кнопка возврата в главное меню
    builder.button(text="🏠 Главное меню", callback_data="back_to_main_menu")
    
    # Располагаем кнопки пагинации в один ряд, а кнопку меню - в другой
    builder.adjust(2, 1)
    
    return builder.as_markup()
