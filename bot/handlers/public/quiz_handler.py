# =================================================================================
# Файл: bot/handlers/public/quiz_handler.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Обрабатывает раздел "Викторина".
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "nav:quiz")
async def handle_quiz_start(call: CallbackQuery, deps: Deps):
    await call.answer("Генерирую вопрос...")
    question_data = await deps.quiz_service.get_random_question()

    if not question_data:
        await call.message.edit_text("🧠 Не удалось сгенерировать вопрос для викторины. Попробуйте позже.", reply_markup=get_back_to_main_menu_keyboard())
        return

    question, options, correct_index = question_data
    
    builder = InlineKeyboardBuilder()
    for i, option_text in enumerate(options):
        # В callback_data передаем 1, если ответ верный, и 0, если нет
        is_correct = 1 if i == correct_index else 0
        builder.button(text=option_text, callback_data=f"quiz_answer:{is_correct}")
    
    builder.adjust(1) # Каждая кнопка в новом ряду
    
    await call.message.edit_text(f"🧠 <b>Вопрос викторины:</b>\n\n{question}", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("quiz_answer:"))
async def handle_quiz_answer(call: CallbackQuery):
    is_correct = int(call.data.split(":")[1])
    
    next_keyboard = InlineKeyboardBuilder()
    next_keyboard.button(text="🔄 Следующий вопрос", callback_data="nav:quiz")
    next_keyboard.button(text="🏠 Главное меню", callback_data="back_to_main_menu")
    next_keyboard.adjust(1)

    if is_correct:
        await call.message.edit_text(f"{call.message.text}\n\n✅ <b>Правильно!</b>", reply_markup=next_keyboard.as_markup())
    else:
        await call.message.edit_text(f"{call.message.text}\n\n❌ <b>Неверно!</b> Попробуйте еще раз.", reply_markup=next_keyboard.as_markup())
    
    await call.answer()
