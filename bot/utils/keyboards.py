# utils/keyboards.py
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import config

def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = {
        "💹 Курс": "menu_price", "⚙️ Топ ASIC": "menu_asics",
        "⛏️ Калькулятор": "menu_calculator", "📰 Новости": "menu_news",
        "😱 Индекс Страха": "menu_fear_greed", "⏳ Халвинг": "menu_halving",
        "📡 Статус BTC": "menu_btc_status", "🧠 Викторина": "menu_quiz",
    }
    for text, data in buttons.items():
        builder.button(text=text, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()

def get_price_keyboard():
    builder = InlineKeyboardBuilder()
    for ticker in config.POPULAR_TICKERS:
        builder.button(text=ticker, callback_data=f"price_{ticker}")
    builder.adjust(len(config.POPULAR_TICKERS))
    builder.row(InlineKeyboardButton(text="➡️ Другая монета", callback_data="price_other"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu"))
    return builder.as_markup()

def get_quiz_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующий вопрос", callback_data="menu_quiz")
    return builder.as_markup()