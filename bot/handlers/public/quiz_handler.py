# ===============================================================
# Файл: bot/handlers/public/quiz_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Обработчик для крипто-викторины с разделенной логикой.
# ===============================================================
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.services.quiz_service import QuizService
from bot.keyboards.quiz_keyboards import get_quiz_keyboard

logger = logging.getLogger(__name__)
router = Router(name="quiz_handler")

async def _send_quiz_poll(message: Message, quiz_service: QuizService):
    """
    Общая функция для генерации и отправки вопроса викторины.
    """
    temp_message = await message.answer("⏳ Генерирую интересный вопрос...")

    question_data = await quiz_service.get_random_question()
    
    await temp_message.delete()
    
    if not question_data:
        await message.answer(
            "😔 Не удалось сгенерировать вопрос. Попробуйте, пожалуйста, позже.",
            reply_markup=get_quiz_keyboard()
        )
        return

    question, options, correct_option_id = question_data
    
    await message.answer_poll(
        question=question, 
        options=options, 
        type='quiz',
        correct_option_id=correct_option_id, 
        is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )

@router.callback_query(F.data == "nav:quiz")
async def handle_quiz_callback(call: CallbackQuery, quiz_service: QuizService):
    """Обрабатывает запуск викторины по нажатию на инлайн-кнопку."""
    # Удаляем предыдущее сообщение с опросом для чистоты интерфейса
    try:
        await call.message.delete()
    except TelegramBadRequest as e:
        logger.warning(f"Could not delete quiz message: {e}")

    # call.message здесь - это сообщение, к которому была привязана кнопка
    await _send_quiz_poll(call.message, quiz_service)


@router.message(F.text == "🧠 Викторина")
async def handle_quiz_message(message: Message, quiz_service: QuizService):
    """Обрабатывает запуск викторины по текстовой команде из меню."""
    await _send_quiz_poll(message, quiz_service)
