from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callback_factories import (
    PriceCallback,
    AsicCallback,
    GameCallback,
    NewsCallback,
    CalculatorCallback,
    MarketCallback,
    CryptoCenterCallback,
    AdminCallback,
    QuizCallback,
)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    # Основные разделы
    kb.button(text="📈 Курс", callback_data=PriceCallback(action="open").pack())
    kb.button(text="🏆 Топ ASIC", callback_data=AsicCallback(action="top").pack())
    kb.button(text="🕹 Игра", callback_data=GameCallback(action="main_menu").pack())
    kb.button(text="📰 Новости", callback_data=NewsCallback(action="sources").pack())
    kb.button(text="🧮 Калькулятор", callback_data=CalculatorCallback(action="start").pack())
    kb.button(text="🛒 Рынок", callback_data=MarketCallback(action="list").pack())
    kb.button(text="🧭 Центр", callback_data=CryptoCenterCallback(action="open").pack())
    kb.button(text="❓ Викторина", callback_data=QuizCallback(action="start").pack())

    # Админ (покажется всем; доступ проверит хендлер)
    kb.button(text="⚙️ Админ", callback_data=AdminCallback(action="menu").pack())

    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()
