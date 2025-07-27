# ===============================================================
# Файл: bot/keyboards/info_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Функции для создания инлайн-клавиатур для
# информационных разделов (курсы, викторина).
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import settings # Для доступа к списку популярных тикеров

def get_price_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для меню запроса курса."""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для популярных тикеров из настроек
    for ticker in settings.mining.popular_tickers:
        builder.button(text=ticker, callback_data=f"price:{ticker}")
    
    builder.button(text="Другая монета...", callback_data="price:other")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    
    # Адаптивная раскладка: по 3 популярных тикера в ряд
    builder.adjust(3, 3, 1, 1) 
    return builder.as_markup()

def get_quiz_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для викторины (для кнопки 'Следующий вопрос')."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Следующий вопрос", callback_data="menu_quiz")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()
