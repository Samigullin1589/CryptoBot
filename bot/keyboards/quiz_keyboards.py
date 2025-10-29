# src/bot/keyboards/quiz_keyboards.py

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from .callback_factories import QuizCallback, MenuCallback

def get_quiz_options_keyboard(options: list, correct_index: int) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с вариантами ответа для вопроса.
    """
    builder = InlineKeyboardBuilder()
    for i, option_text in enumerate(options):
        is_correct = 1 if i == correct_index else 0
        builder.button(
            text=str(option_text), 
            callback_data=QuizCallback(action="answer", is_correct=is_correct).pack()
        )
    builder.adjust(1)
    return builder.as_markup()

def get_quiz_next_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для перехода к следующему вопросу или в меню.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Следующий вопрос", callback_data=MenuCallback(level=0, action="quiz").pack())
    builder.button(text="🏠 Главное меню", callback_data=MenuCallback(level=0, action="main").pack())
    builder.adjust(1)
    return builder.as_markup()