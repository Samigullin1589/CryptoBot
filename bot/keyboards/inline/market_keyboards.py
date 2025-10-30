# bot/keyboards/inline/market_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_market_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура главного меню рыночной информации
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Обзор рынка",
                    callback_data="market_overview"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⛏ Статус сети BTC",
                    callback_data="btc_network_status"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="main_menu"
                )
            ]
        ]
    )
    return keyboard