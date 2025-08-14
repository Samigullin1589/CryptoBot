# ===============================================================
# Файл: bot/keyboards/mining_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ ВОССТАНОВЛЕННАЯ)
# Описание: Генераторы клавиатур для игры "Виртуальный Майнинг" и Калькулятора.
# ИСПРАВЛЕНИЕ: Переход на использование фабрик CallbackData.
# ===============================================================

from typing import List, Dict
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name
from .callback_factories import MenuCallback, GameCallback, PaginatorCallback, CalculatorCallback

PAGE_SIZE = 5

# --- Клавиатуры для игры "Виртуальный Майнинг" ---

def get_mining_menu_keyboard(is_session_active: bool) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру главного меню игры, динамически отображая
    кнопку начала сессии.
    """
    builder = InlineKeyboardBuilder()
    
    if not is_session_active:
        builder.button(text="▶️ Начать сессию", callback_data=GameCallback(action="shop").pack())
    
    builder.button(text="🏠 Моя ферма", callback_data=GameCallback(action="my_farm").pack())
    builder.button(text="💡 Электричество", callback_data=GameCallback(action="electricity").pack())
    builder.button(text="🤝 Пригласить друга", callback_data=GameCallback(action="invite").pack())
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
            callback_data=GameCallback(action="start", value=asic_id).pack()
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=GameCallback(action="shop_page", page=page - 1).pack()))
    
    total_pages = (len(asics) + PAGE_SIZE - 1) // PAGE_SIZE
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="do_nothing"))

    if end_offset < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=GameCallback(action="shop_page", page=page + 1).pack()))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data=GameCallback(action="main_menu").pack()))
    builder.adjust(1)
    return builder.as_markup()

def get_confirm_purchase_keyboard(item_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения покупки. Совместима с импортом в mining_game_handler.
    Callback'и оформлены через фабрику GameCallback:
    - action="buy_confirm" для подтверждения
    - action="buy_cancel" для отмены
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Купить", callback_data=GameCallback(action="buy_confirm", value=item_id).pack())
    builder.button(text="❌ Отмена", callback_data=GameCallback(action="buy_cancel", value=item_id).pack())
    builder.adjust(2)
    return builder.as_markup()

def get_my_farm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Вывести средства", callback_data=GameCallback(action="withdraw").pack())
    builder.button(text="⬅️ Назад в меню", callback_data=GameCallback(action="main_menu").pack())
    builder.adjust(1)
    return builder.as_markup()

def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Понятно", callback_data=GameCallback(action="main_menu").pack())
    return builder.as_markup()

def get_electricity_menu_keyboard(tariffs: dict, user_tariffs: List[str], current_tariff: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name, info in tariffs.items():
        if name in user_tariffs:
            status = " (Выбран)" if name == current_tariff else " (Доступен)"
            callback = GameCallback(action="tariff_select", value=name).pack()
        else:
            status = f" ({info.unlock_price} монет)"
            callback = GameCallback(action="tariff_buy", value=name).pack()
        builder.button(text=f"{name}{status}", callback_data=callback)
    
    builder.button(text="⬅️ Назад в меню", callback_data=GameCallback(action="main_menu").pack())
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатуры для Калькулятора доходности ---

def get_calculator_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_fsm")
    return builder.as_markup()

def get_currency_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="USD ($)", callback_data=CalculatorCallback(action="currency", value="usd").pack())
    builder.button(text="RUB (₽)", callback_data=CalculatorCallback(action="currency", value="rub").pack())
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    builder.adjust(2)
    return builder.as_markup()

def get_asic_selection_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = page * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    for i, asic in enumerate(asics[start_offset:end_offset], start=start_offset):
        builder.button(text=asic.name, callback_data=CalculatorCallback(action="select_asic", asic_index=i).pack())

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=CalculatorCallback(action="page", page=page - 1).pack()))
    if end_offset < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=CalculatorCallback(action="page", page=page + 1).pack()))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    builder.adjust(1)
    return builder.as_markup()

def get_calculator_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Новый расчёт", callback_data=MenuCallback(level=1, action="calculator").pack())
    builder.button(text="🏠 Главное меню", callback_data=MenuCallback(level=0, action="main").pack())
    builder.adjust(1)
    return builder.as_markup()
