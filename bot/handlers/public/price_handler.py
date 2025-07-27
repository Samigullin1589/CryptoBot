# ===============================================================
# Файл: bot/handlers/public/price_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Обрабатывает все взаимодействия, связанные с получением
# цен на криптовалюты. Управляет сценарием FSM для запроса
# тикера у пользователя.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.info_keyboards import get_price_keyboard
from bot.services.price_service import PriceService
# --- ИСПРАВЛЕНИЕ: Используем правильное имя класса (в единственном числе) ---
from bot.states.info_states import PriceInquiryState
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.formatters import format_price_info
from bot.utils.ui_helpers import show_main_menu_from_callback

# Инициализация роутера
router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- ОБРАБОТЧИКИ СЦЕНАРИЯ ЗАПРОСА ЦЕНЫ ---

@router.callback_query(F.data == "nav:price")
async def handle_price_menu(call: CallbackQuery, state: FSMContext):
    """
    Отображает меню выбора популярных криптовалют или ввода своей.
    Запускает сценарий FSM.
    """
    await state.clear()
    text = "Курс какой монеты вас интересует?"
    await call.message.edit_text(text, reply_markup=get_price_keyboard())
    # --- ИСПРАВЛЕНИЕ: Используем правильное имя класса ---
    await state.set_state(PriceInquiryState.waiting_for_ticker)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

@router.callback_query(F.data.startswith("price:"))
async def handle_price_button_callback(call: CallbackQuery, state: FSMContext, price_service: PriceService):
    """
    Обрабатывает нажатие на кнопку с конкретной монетой (BTC, ETH и т.д.).
    """
    await state.clear() # Сценарий завершен, так как тикер получен
    query = call.data.split(':')[1]
    
    await call.message.edit_text(f"⏳ Получаю курс для {query.upper()}...")
    
    price_info = await price_service.get_crypto_price(query)
    if price_info:
        response_text = format_price_info(price_info)
        await call.message.edit_text(response_text, reply_markup=get_main_menu_keyboard())
    else:
        await call.message.edit_text(
            f"❌ К сожалению, не удалось найти информацию по тикеру '{query}'.",
            reply_markup=get_main_menu_keyboard()
        )

# --- ИСПРАВЛЕНИЕ: Используем правильное имя класса ---
@router.message(PriceInquiryState.waiting_for_ticker)
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
async def process_ticker_input_from_user(message: Message, state: FSMContext, price_service: PriceService):
    """
    Обрабатывает текстовый ввод тикера от пользователя,
    находясь в состоянии waiting_for_ticker.
    """
    await state.clear() # Сценарий завершен
    temp_msg = await message.answer("⏳ Получаю курс...")
    
    price_info = await price_service.get_crypto_price(message.text)
    if price_info:
        response_text = format_price_info(price_info)
        await temp_msg.edit_text(response_text, reply_markup=get_main_menu_keyboard())
    else:
        await temp_msg.edit_text(
            f"❌ К сожалению, не удалось найти информацию по тикеру '{message.text}'.",
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(PriceInquiryState.waiting_for_ticker, F.data == "nav:back_to_main")
async def cancel_price_inquiry(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает отмену сценария запроса цены и возвращает в главное меню.
    """
    await state.clear()
    await show_main_menu_from_callback(call)
