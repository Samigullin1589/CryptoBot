# ===============================================================
# Файл: bot/keyboards/mining_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ ВОССТАНОВЛЕННАЯ)
# Описание: Генераторы клавиатур для игры "Виртуальный Майнинг" и Калькулятора.
# ИСПРАВЛЕНИЕ: Восстановлены все недостающие функции для
#              корректной работы игрового модуля.
# ===============================================================

from typing import List, Dict
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name
from .callback_factories import MenuCallback

PAGE_SIZE = 5 # Количество асиков на одной странице

# --- Клавиатуры для игры "Виртуальный Майнинг" ---

def get_mining_menu_keyboard(is_session_active: bool) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру главного меню игры, динамически отображая
    кнопку начала сессии.
    """
    builder = InlineKeyboardBuilder()
    
    if not is_session_active:
        builder.button(text="▶️ Начать сессию", callback_data="game_nav:shop")
    
    builder.button(text="🏠 Моя ферма", callback_data="game_nav:my_farm")
    builder.button(text="💡 Электричество", callback_data="game_nav:electricity")
    builder.button(text="🤝 Пригласить друга", callback_data="game_action:invite")
    builder.button(text="⬅️ Назад в меню", callback_data=MenuCallback(level=0, action="main").pack())
    
    builder.adjust(1 if not is_session_active else 2, 2, 1)
    return builder.as_markup()

def get_shop_keyboard(asics: List[AsicMiner], page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = page * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE
    
    for asic in asics[start_offset:end_offset]:
        asic_id = normalize_asic_name(asic.name)
        profit_str = f"{asic.profitability:,.2f}$/день" if asic.profitability is not None else ""
        builder.button(
            text=f"Купить {asic.name} {profit_str}",
            callback_data=f"game_action:start:{asic_id}"
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"game_shop_page:{page - 1}"))
    
    total_pages = (len(asics) + PAGE_SIZE - 1) // PAGE_SIZE
    if total_pages > 1:
         nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="do_nothing"))

    if end_offset < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"game_shop_page:{page + 1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="nav:mining_game"))
    builder.adjust(1)
    return builder.as_markup()

def get_my_farm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Вывести средства", callback_data="game_action:withdraw")
    builder.button(text="⬅️ Назад в меню", callback_data="nav:mining_game")
    builder.adjust(1)
    return builder.as_markup()

def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Понятно", callback_data="nav:mining_game")
    return builder.as_markup()

def get_electricity_menu_keyboard(tariffs: dict, user_tariffs: List[str], current_tariff: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name, info in tariffs.items():
        if name in user_tariffs:
            status = " (Выбран)" if name == current_tariff else " (Доступен)"
            callback = f"game_tariff_select:{name}"
        else:
            status = f" ({info.unlock_price} монет)"
            callback = f"game_tariff_buy:{name}"
        builder.button(text=f"{name}{status}", callback_data=callback)
    
    builder.button(text="⬅️ Назад в меню", callback_data="nav:mining_game")
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатуры для Калькулятора доходности ---

def get_calculator_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="calc_action:cancel")
    return builder.as_markup()

def get_currency_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="USD ($)", callback_data="calc_currency:usd")
    builder.button(text="RUB (₽)", callback_data="calc_currency:rub")
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="calc_action:cancel"))
    builder.adjust(2)
    return builder.as_markup()

def get_asic_selection_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = page * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    for i, asic in enumerate(asics[start_offset:end_offset], start=start_offset):
        builder.button(text=asic.name, callback_data=f"calc_select_asic:{i}")

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"calc_page:{page - 1}"))
    if end_offset < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"calc_page:{page + 1}"))
    
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="calc_action:cancel"))
    builder.adjust(1)
    return builder.as_markup()

def get_calculator_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Новый расчёт", callback_data="nav:calculator")
    builder.button(text="🏠 Главное меню", callback_data=MenuCallback(level=0, action="main").pack())
    builder.adjust(1)
    return builder.as_markup()