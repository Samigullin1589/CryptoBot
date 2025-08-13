# =================================================================================
# Файл: bot/keyboards/market_keyboards.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНАЯ)
# Описание: Функции для генерации всех необходимых клавиатур для рынка.
# ИСПРАВЛЕНИЕ: Удалена устаревшая константа MARKET_CALLBACK_PREFIX.
# =================================================================================

from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.models import MarketListing, AsicMiner
from .callback_factories import MarketCallback

def get_market_listings_keyboard(listings: List[MarketListing], current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для отображения списка лотов на рынке с постраничной навигацией.
    """
    builder = InlineKeyboardBuilder()

    # Создаем по одной кнопке для каждого лота
    for listing in listings:
        asic = AsicMiner.model_validate_json(listing.asic_data)
        button_text = f"Купить {asic.name} за {listing.price:,.2f} монет"
        callback_data = MarketCallback(action="buy", listing_id=listing.id).pack()
        builder.row(InlineKeyboardButton(text=button_text, callback_data=callback_data))

    # Создаем навигационные кнопки
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=MarketCallback(action="page", page=current_page - 1).pack()))
    
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="do_nothing")) # Просто для отображения

    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=MarketCallback(action="page", page=current_page + 1).pack()))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="Продать своё оборудование", callback_data=MarketCallback(action="sell_start").pack()))
    
    return builder.as_markup()

def get_choose_asic_to_sell_keyboard(user_asics: List[AsicMiner]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора ASIC'а, который пользователь хочет продать.
    """
    builder = InlineKeyboardBuilder()
    for asic in user_asics:
        builder.row(InlineKeyboardButton(
            text=f"Продать {asic.name}",
            callback_data=MarketCallback(action="sell_select", asic_id=asic.id).pack()
        ))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel_fsm"))
    return builder.as_markup()

def get_confirm_buy_keyboard(listing_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для подтверждения покупки.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить покупку", callback_data=MarketCallback(action="buy_confirm", listing_id=listing_id).pack())
    builder.button(text="❌ Отмена", callback_data=MarketCallback(action="buy_cancel").pack())
    builder.adjust(2)
    return builder.as_markup()