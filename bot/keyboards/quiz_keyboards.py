# ===============================================================
# Файл: bot/keyboards/quiz_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Генераторы клавиатур для викторины.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_quiz_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для опроса в викторине.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Следующий вопрос", callback_data="nav:quiz")
    builder.button(text="⬅️ Главное меню", callback_data="nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()
