# ===============================================================
# Файл: bot/handlers/public/quiz_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчик для запуска крипто-викторины.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.info_keyboards import get_quiz_keyboard
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.quiz_service import QuizService
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "menu_quiz")
@router.message(F.text == "🧠 Викторина")
async def handle_quiz_menu(update: Union[CallbackQuery, Message], quiz_service: QuizService, admin_service: AdminService):
    """
    Обрабатывает запуск викторины.
    """
    await admin_service.track_command_usage("🧠 Викторина")
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        try:
            await update.message.delete()
        except TelegramBadRequest:
            pass # Если не удалось удалить, ничего страшного

    temp_message = await message.answer("⏳ Генерирую вопрос...")

    question, options, correct_option_id = await quiz_service.get_random_question()
    
    if not options:
        await temp_message.edit_text(question, reply_markup=get_main_menu_keyboard())
        return
    
    await temp_message.delete()
    
    await message.answer_poll(
        question=question, 
        options=options, 
        type='quiz',
        correct_option_id=correct_option_id, 
        is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )
    
    if isinstance(update, CallbackQuery):
        await update.answer()
