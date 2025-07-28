# ===============================================================
# Файл: bot/handlers/public/quiz_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Обработчик для команды викторины.
# ===============================================================
import logging
from typing import Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.services.quiz_service import QuizService
from bot.keyboards.info_keyboards import get_quiz_keyboard
# --- ИСПРАВЛЕНИЕ: Импортируем из правильного места ---
from bot.utils.ui_helpers import get_message_and_chat_id

logger = logging.getLogger(__name__)
router = Router(name="quiz_handler")

@router.callback_query(F.data == "nav:quiz")
@router.message(F.text == "🧠 Викторина")
async def handle_quiz_menu(update: Union[CallbackQuery, Message], quiz_service: QuizService):
    """
    Обрабатывает запуск викторины. Генерирует вопрос и отправляет его в виде опроса.
    """
    message, _ = await get_message_and_chat_id(update)
    
    # Если пользователь нажал на кнопку, удаляем старое сообщение
    if isinstance(update, CallbackQuery):
        try:
            await update.message.delete()
        except TelegramBadRequest:
            pass

    temp_message = await message.answer("⏳ Генерирую интересный вопрос...")

    question, options, correct_option_id = await quiz_service.get_random_question()
    
    # Удаляем временное сообщение "Генерирую..."
    await temp_message.delete()
    
    # Отправляем вопрос в виде опроса
    await message.answer_poll(
        question=question, 
        options=options, 
        type='quiz',
        correct_option_id=correct_option_id, 
        is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )
