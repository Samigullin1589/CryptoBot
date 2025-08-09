# =================================================================================
# Файл: bot/keyboards/info_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025, С ФАБРИКАМИ)
# Описание: Клавиатуры для информационных разделов.
# ИСПРАВЛЕНИЕ: Переход на использование PriceCallback и MenuCallback.
# =================================================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

# Импортируем наши новые фабрики
from .callback_factories import PriceCallback, MenuCallback

def get_price_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для меню запроса цен с использованием фабрик."""
    builder = InlineKeyboardBuilder()
    
    # Кнопки для популярных монет используют PriceCallback
    popular_coins = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "TON": "the-open-network"
    }
    for symbol, coin_id in popular_coins.items():
        builder.button(
            text=symbol, 
            callback_data=PriceCallback(action="show", coin_id=coin_id)
        )
    
    # Кнопка для возврата в главное меню использует MenuCallback
    builder.button(
        text="⬅️ Назад в меню", 
        callback_data=MenuCallback(level=0, action="main")
    )
    
    builder.adjust(4, 1)
    return builder.as_markup()
