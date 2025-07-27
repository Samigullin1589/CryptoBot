# ===============================================================
# Файл: bot/keyboards/asic_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Функции для создания инлайн-клавиатур, связанных
# с функционалом ASIC.
# ===============================================================
from typing import List, Dict, Any
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_top_asics_keyboard(page: int, total_pages: int, sort_by: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для навигации по страницам топа ASIC.
    
    :param page: Текущая страница.
    :param total_pages: Всего страниц.
    :param sort_by: Текущий метод сортировки.
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки пагинации
    prev_page = page - 1 if page > 1 else total_pages
    next_page = page + 1 if page < total_pages else 1
    
    builder.button(text="◀️ Пред.", callback_data=f"top_asics:page:{prev_page}:{sort_by}")
    builder.button(text=f"Страница {page}/{total_pages}", callback_data="do_nothing")
    builder.button(text="След. ▶️", callback_data=f"top_asics:page:{next_page}:{sort_by}")

    # Кнопки сортировки
    new_sort_by = "efficiency" if sort_by == "profitability" else "profitability"
    sort_text = "⚡️ По эффективности" if sort_by == "profitability" else "💰 По доходности"
    builder.button(text=sort_text, callback_data=f"top_asics:page:1:{new_sort_by}")
    
    builder.adjust(3, 1)
    return builder.as_markup()

def get_electricity_tariff_keyboard(tariffs: Dict[str, Any]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора тарифа на электроэнергию.
    
    :param tariffs: Словарь с тарифами из настроек.
    """
    builder = InlineKeyboardBuilder()
    for tariff_name in tariffs.keys():
        builder.button(text=tariff_name, callback_data=f"set_tariff:{tariff_name}")
    
    builder.adjust(1)
    return builder.as_markup()
