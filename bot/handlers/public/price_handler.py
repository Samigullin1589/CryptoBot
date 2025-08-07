# =================================================================================
# Файл: bot/handlers/public/price_handler.py (ВЕРСЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Обрабатывает все взаимодействия, связанные с получением
# цен на криптовалюты, с использованием FSM и инъекции зависимостей.
# ИСПРАВЛЕНИЕ: Логика полностью переписана для соответствия DI и
# устранения "зависания" кнопок.
# =================================================================================
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.keyboards.info_keyboards import get_price_keyboard
from bot.states.info_states import PriceInquiryState
from bot.utils.dependencies import Deps
from bot.utils.formatters import format_price_info
from bot.utils.ui_helpers import show_main_menu_from_callback

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
    text = "Курс какой монеты вас интересует? Выберите из популярных или отправьте тикер/название."
    await call.message.edit_text(text, reply_markup=get_price_keyboard())
    await state.set_state(PriceInquiryState.waiting_for_ticker)
    await call.answer() # <-- Отвечаем на callback, чтобы убрать "часики"

@router.callback_query(F.data.startswith("price:"))
async def handle_price_button_callback(call: CallbackQuery, state: FSMContext, deps: Deps):
    """
    Обрабатывает нажатие на кнопку с конкретной монетой (BTC, ETH и т.д.).
    """
    await state.clear()
    coin_id = call.data.split(':')[1]
    
    await call.answer(f"⏳ Получаю курс для {coin_id.upper()}...")
    
    # Используем новые сервисы
    coin = await deps.coin_list_service.find_coin_by_query(coin_id)
    prices = await deps.price_service.get_prices([coin.id]) if coin else {}
    price_value = prices.get(coin.id)
    
    if coin and price_value is not None:
        response_text = format_price_info(coin, {"price": price_value})
        await call.message.edit_text(response_text, reply_markup=get_back_to_main_menu_keyboard())
    else:
        await call.message.edit_text(
            f"❌ К сожалению, не удалось найти информацию по '{coin_id}'.",
            reply_markup=get_back_to_main_menu_keyboard()
        )

@router.message(PriceInquiryState.waiting_for_ticker)
async def process_ticker_input_from_user(message: Message, state: FSMContext, deps: Deps):
    """
    Обрабатывает текстовый ввод тикера от пользователя.
    """
    await state.clear()
    temp_msg = await message.answer("⏳ Ищу монету и получаю курс...")
    query = message.text.strip()
    
    coin = await deps.coin_list_service.find_coin_by_query(query)
    if not coin:
        await temp_msg.edit_text(f"❌ Не удалось найти монету по запросу '{query}'. Попробуйте еще раз.", reply_markup=get_back_to_main_menu_keyboard())
        return

    prices = await deps.price_service.get_prices([coin.id])
    price_value = prices.get(coin.id)

    if price_value is not None:
        response_text = format_price_info(coin, {"price": price_value})
        await temp_msg.edit_text(response_text, reply_markup=get_back_to_main_menu_keyboard())
    else:
        await temp_msg.edit_text(f"❌ Не удалось найти информацию по '{query}'.", reply_markup=get_back_to_main_menu_keyboard())

@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main_menu(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает отмену любого сценария и возвращает в главное меню.
    """
    await state.clear()
    await show_main_menu_from_callback(call)
    await call.answer()
