# ===============================================================
# Файл: bot/handlers/public/price_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчики для всего, что связано с курсами валют.
# Использует FSM и делегирует логику в сервисы.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.info_keyboards import get_price_keyboard
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.price_service import PriceService
from bot.services.admin_service import AdminService
from bot.states.info_states import PriceInquiryStates
from bot.utils.formatters import format_price_info
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "menu_price")
@router.message(F.text == "💹 Курс")
async def handle_price_menu(update: Union[CallbackQuery, Message], state: FSMContext, admin_service: AdminService):
    """
    Обрабатывает вход в меню курсов, сбрасывает предыдущее состояние
    и предлагает выбрать монету.
    """
    await admin_service.track_command_usage("💹 Курс")
    await state.clear() # Гарантируем, что мы в чистом состоянии

    message, _ = await get_message_and_chat_id(update)
    await message.answer("Курс какой монеты вас интересует?", reply_markup=get_price_keyboard())
    await state.set_state(PriceInquiryStates.waiting_for_ticker)
    
    if isinstance(update, CallbackQuery):
        await update.answer()

@router.callback_query(F.data.startswith("price:"))
async def handle_price_ticker_callback(call: CallbackQuery, state: FSMContext, price_service: PriceService, admin_service: AdminService):
    """
    Обрабатывает нажатие на кнопку с конкретным тикером или 'Другая монета'.
    """
    await call.answer()
    ticker = call.data.split(":")[1]

    if ticker == "other":
        await call.message.edit_text("Введите тикер монеты (напр. Aleo):")
        # Состояние уже установлено, просто ждем ввода
        return

    await state.clear()
    await admin_service.track_command_usage(f"Курс (кнопка): {ticker.upper()}")
    await call.message.edit_text(f"⏳ Получаю курс для {ticker.upper()}...")
    
    coin = await price_service.get_crypto_price(ticker)
    if not coin:
        response_text = f"❌ Не удалось найти информацию по тикеру '{ticker}'."
    else:
        response_text = format_price_info(coin)
    
    await call.message.edit_text(response_text, reply_markup=get_main_menu_keyboard())

@router.message(PriceInquiryStates.waiting_for_ticker)
async def process_ticker_text_input(message: Message, state: FSMContext, price_service: PriceService, admin_service: AdminService):
    """
    Обрабатывает текстовый ввод тикера от пользователя, находящегося в состоянии ожидания.
    """
    await state.clear()
    ticker = message.text.strip()
    await admin_service.track_command_usage(f"Курс (текст): {ticker}")
    
    temp_msg = await message.answer(f"⏳ Получаю курс для '{ticker}'...")
    
    coin = await price_service.get_crypto_price(ticker)
    if not coin:
        response_text = f"❌ Не удалось найти информацию по тикеру '{ticker}'."
    else:
        response_text = format_price_info(coin)
        
    await temp_msg.edit_text(response_text, reply_markup=get_main_menu_keyboard())
