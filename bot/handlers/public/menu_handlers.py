# =================================================================================
# Файл: bot/handlers/public/menu_handlers.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Центральный обработчик для всех кнопок главного меню.
# Устраняет проблему "зависания" кнопок.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_main_menu_keyboard, get_back_to_main_menu_keyboard
from bot.keyboards.info_keyboards import get_price_keyboard
from bot.states.info_states import PriceInquiryState
from bot.utils.formatters import format_price_info

router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- ОБРАБОТЧИК ВОЗВРАТА В ГЛАВНОЕ МЕНЮ ---
@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "👋 Выберите одну из опций в меню ниже."
    await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await call.answer()

# --- РАЗДЕЛ: КУРСЫ ВАЛЮТ (перенесен из price_handler) ---
@router.callback_query(F.data == "nav:price")
async def handle_price_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "Курс какой монеты вас интересует? Выберите из популярных или отправьте тикер/название."
    await call.message.edit_text(text, reply_markup=get_price_keyboard())
    await state.set_state(PriceInquiryState.waiting_for_ticker)
    await call.answer()

# --- ОБРАБОТЧИКИ-ЗАГЛУШКИ ДЛЯ ОСТАЛЬНЫХ КНОПОК МЕНЮ ---
@router.callback_query(F.data.startswith("nav:"))
async def handle_placeholder_menu(call: CallbackQuery):
    """Отвечает на все остальные кнопки 'nav:*', которые еще не реализованы."""
    # Исключаем уже реализованный 'nav:price'
    if call.data == "nav:price":
        return
        
    destination = call.data.split(":")[1]
    await call.answer(f"Раздел '{destination}' находится в разработке.", show_alert=True)
