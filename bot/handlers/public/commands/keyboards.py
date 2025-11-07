# bot/handlers/public/commands/keyboards.py
"""
Клавиатуры для команд.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает главную клавиатуру."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Цены"),
                KeyboardButton(text="⛏ Майнинг")
            ],
            [
                KeyboardButton(text="📊 Рынок"),
                KeyboardButton(text="🎮 Игра")
            ],
            [
                KeyboardButton(text="🧠 Квиз"),
                KeyboardButton(text="🏆 Достижения")
            ],
            [
                KeyboardButton(text="👥 Рефералы"),
                KeyboardButton(text="💎 Премиум")
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="⚙️ Настройки")
            ],
        ],
        resize_keyboard=True
    )