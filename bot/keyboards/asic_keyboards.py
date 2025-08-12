# ===============================================================
# Файл: bot/keyboards/asic_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Генераторы клавиатур для раздела ASIC-майнеров.
# ИСПРАВЛЕНИЕ: Исправлена логика создания кнопок для
#              совместимости с aiogram.utils.keyboard.InlineKeyboardBuilder
# ===============================================================

from typing import List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name

PAGE_SIZE = 5

def get_top_asics_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = (page - 1) * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    # Добавляем кнопки для каждого ASIC на текущей странице
    for asic in asics[start_offset:end_offset]:
        asic_id = normalize_asic_name(asic.name)
        builder.button(
            text=f"{asic.name} - ${asic.net_profit:.2f}/день",
            callback_data=f"asic_passport:{asic_id}"
        )
    
    # Собираем кнопки навигации в отдельный список
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"asic_page:{page - 1}"))
    if end_offset < len(asics):
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"asic_page:{page + 1}"))
    
    # Добавляем ряд с кнопками навигации, если они есть
    if nav_row:
        builder.row(*nav_row)

    # Добавляем ряд с кнопками действий
    builder.row(
        InlineKeyboardButton(text="💡 Указать цену э/э", callback_data="asic_action:set_cost"),
        InlineKeyboardButton(text="⬅️ В меню", callback_data="nav:main_menu")
    )
    
    # Располагаем кнопки ASIC по одной в ряду
    builder.adjust(1)
    return builder.as_markup()

def get_asic_passport_keyboard(page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к списку", callback_data=f"asic_page:{page}")
    return builder.as_markup()