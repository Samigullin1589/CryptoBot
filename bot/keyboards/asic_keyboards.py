# ===============================================================
# Файл: bot/keyboards/asic_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Генераторы клавиатур для раздела ASIC-майнеров.
# ===============================================================

from typing import List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name

PAGE_SIZE = 5

def get_top_asics_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = (page - 1) * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    for asic in asics[start_offset:end_offset]:
        asic_id = normalize_asic_name(asic.name)
        builder.button(
            text=f"{asic.name} - ${asic.net_profit:.2f}/день",
            callback_data=f"asic_passport:{asic_id}"
        )
    
    nav_row = []
    if page > 1:
        nav_row.append(builder.button(text="⬅️ Назад", callback_data=f"asic_page:{page - 1}"))
    if end_offset < len(asics):
        nav_row.append(builder.button(text="Вперед ➡️", callback_data=f"asic_page:{page + 1}"))
    
    builder.row(*nav_row)
    builder.row(
        builder.button(text="💡 Указать цену э/э", callback_data="asic_action:set_cost"),
        builder.button(text="⬅️ В меню", callback_data="nav:main_menu")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_asic_passport_keyboard(page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к списку", callback_data=f"asic_page:{page}")
    return builder.as_markup()
