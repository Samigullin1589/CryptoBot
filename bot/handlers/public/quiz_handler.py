# =================================================================================
# Файл: bot/handlers/public/quiz_handler.py (ВЕРСЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Обрабатывает раздел "Викторина".
# ИСПРАВЛЕНИЕ: Внедрение зависимостей унифицировано через deps: Deps.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery
from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.keyboards.callback_factories import MenuCallback, QuizCallback
from bot.keyboards.quiz_keyboards import get_quiz_options_keyboard, get_quiz_next_keyboard

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(MenuCallback.filter(F.action == "quiz"))
async def handle_quiz_start(call: CallbackQuery, deps: Deps):
    await call.answer("Генерирую вопрос...")
    question_data = await deps.quiz_service.get_random_question()

    if not question_data:
        await call.message.edit_text("🧠 Не удалось сгенерировать вопрос для викторины. Попробуйте позже.", reply_markup=get_back_to_main_menu_keyboard())
        return

    question, options, correct_index = question_data
    
    keyboard = get_quiz_options_keyboard(options, correct_index)
    
    await call.message.edit_text(f"🧠 <b>Вопрос викторины:</b>\n\n{question}", reply_markup=keyboard)

@router.callback_query(QuizCallback.filter(F.action == "answer"))
async def handle_quiz_answer(call: CallbackQuery, callback_data: QuizCallback):
    is_correct = callback_data.is_correct
    
    next_keyboard = get_quiz_next_keyboard()

    if is_correct:
        await call.message.edit_text(f"{call.message.text}\n\n✅ <b>Правильно!</b>", reply_markup=next_keyboard)
    else:
        await call.message.edit_text(f"{call.message.text}\n\n❌ <b>Неверно!</b> Попробуйте еще раз.", reply_markup=next_keyboard)
    
    await call.answer()
