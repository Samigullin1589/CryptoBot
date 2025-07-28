# ===============================================================
# Файл: bot/keyboards/asic_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Функции для создания инлайн-клавиатур, связанных
# с просмотром и выбором ASIC-майнеров.
# ===============================================================
from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.utils.models import AsicMiner

ITEMS_PER_PAGE = 8

def get_top_asics_keyboard(asics: List[AsicMiner], page: int, sort_by: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для навигации по списку топ ASIC-майнеров.
    Включает пагинацию и кнопки сортировки.
    """
    builder = InlineKeyboardBuilder()
    
    start_index = (page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    
    # Кнопки для каждого ASIC'а на странице
    for asic in asics[start_index:end_index]:
        builder.button(
            text=f"{asic.name} (${asic.profitability:.2f}/день)",
            callback_data=f"asic_passport:{asic.name}"
        )
    builder.adjust(1)
    
    # Кнопки пагинации
    nav_row = []
    if page > 1:
        nav_row.append(builder.button(text="◀️ Пред.", callback_data=f"top_asics:page:{page - 1}:{sort_by}"))
    if end_index < len(asics):
        nav_row.append(builder.button(text="След. ▶️", callback_data=f"top_asics:page:{page + 1}:{sort_by}"))
    
    if nav_row:
        builder.row(*nav_row)

    # Кнопки сортировки
    sort_profit_text = "✅ По доходности" if sort_by == "profitability" else "По доходности"
    sort_eff_text = "✅ По эффективности" if sort_by == "efficiency" else "По эффективности"
    
    builder.row(
        builder.button(text=sort_profit_text, callback_data="top_asics:sort:profitability:0"),
        builder.button(text=sort_eff_text, callback_data="top_asics:sort:efficiency:0")
    )
    
    # Кнопка возврата в главное меню
    builder.row(builder.button(text="⬅️ Назад в главное меню", callback_data="nav:main_menu"))
    
    return builder.as_markup()

def get_asic_passport_keyboard(page: int, sort_by: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для экрана "паспорта" ASIC.
    Основная функция - возврат к списку топа.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад к списку",
        callback_data=f"top_asics:page:{page}:{sort_by}"
    )
    return builder.as_markup()
