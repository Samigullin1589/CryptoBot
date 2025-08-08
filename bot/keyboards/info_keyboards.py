# =================================================================================
# Файл: bot/keyboards/info_keyboards.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Клавиатуры для информационных разделов, таких как курсы валют.
# ИСПРАВЛЕНИЕ: Удалена зависимость от несуществующей конфигурации 'settings.mining'.
# =================================================================================

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_price_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для меню запроса цен."""
    builder = InlineKeyboardBuilder()
    
    # Кнопки для популярных монет определены прямо здесь для простоты и надежности
    builder.button(text="BTC", callback_data="price:bitcoin")
    builder.button(text="ETH", callback_data="price:ethereum")
    builder.button(text="SOL", callback_data="price:solana")
    builder.button(text="BNB", callback_data="price:binancecoin")
    
    # Кнопка для возврата в главное меню
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    
    builder.adjust(4, 1) # 4 кнопки монет в ряд, 1 кнопка назад
    return builder.as_markup()
