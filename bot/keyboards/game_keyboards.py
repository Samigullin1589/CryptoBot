# =================================================================================
# Файл: bot/keyboards/game_keyboards.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Клавиатуры для раздела "Виртуальный Майнинг".
# =================================================================================
from typing import List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.utils.models import AsicMiner

ASICS_PER_PAGE = 5

def get_game_main_menu_keyboard(is_session_active: bool) -> InlineKeyboardMarkup:
    """Создает главное меню игрового раздела."""
    builder = InlineKeyboardBuilder()
    if not is_session_active:
        builder.button(text="▶️ Начать сессию", callback_data="game:start_session")
    
    builder.button(text="🛠 Ангар", callback_data="game:hangar")
    builder.button(text="🛒 Рынок", callback_data="game:market")
    builder.button(text="💡 Тарифы э/э", callback_data="game:tariffs")
    builder.button(text="🏆 Таблица лидеров", callback_data="game:leaderboard")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main_menu")
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_hangar_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для ангара с выбором ASIC для запуска сессии."""
    builder = InlineKeyboardBuilder()
    
    total_pages = (len(asics) + ASICS_PER_PAGE - 1) // ASICS_PER_PAGE
    start_index = page * ASICS_PER_PAGE
    end_index = start_index + ASICS_PER_PAGE

    if not asics:
        builder.button(text="🛒 Перейти на рынок", callback_data="game:market")
    else:
        for asic in asics[start_index:end_index]:
            builder.button(text=f"▶️ {asic.name}", callback_data=f"game_start:{asic.id}")
    
    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(builder.button(text="⬅️", callback_data=f"hangar_page:{page - 1}"))
    if end_index < len(asics):
        nav_buttons.append(builder.button(text="➡️", callback_data=f"hangar_page:{page + 1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(builder.button(text="⬅️ Назад в меню игры", callback_data="nav:mining_game"))
    return builder.as_markup()
