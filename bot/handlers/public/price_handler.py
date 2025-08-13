# =================================================================================
# Файл: bot/handlers/public/price_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - РЕФАКТОРИНГ)
# Описание: Обработчик для сценария получения цены.
# ИСПРАВЛЕНИЕ: Добавлен фильтр MenuCallback для прямого отклика на кнопку меню.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.keyboards.info_keyboards import get_price_keyboard
from bot.keyboards.callback_factories import PriceCallback, MenuCallback
from bot.states.info_states import PriceInquiryState
from bot.utils.dependencies import Deps
from bot.utils.formatters import format_price_info

router = Router(name="price_handler_router")
logger = logging.getLogger(__name__)

@router.callback_query(MenuCallback.filter(F.action == "price"))
async def handle_price_menu_start(call: CallbackQuery, state: FSMContext, **kwargs):
    """Точка входа в раздел курсов, вызывается из главного меню."""
    text = "Курс какой монеты вас интересует? Выберите из популярных или отправьте тикер/название."
    await call.message.edit_text(text, reply_markup=get_price_keyboard())
    await state.set_state(PriceInquiryState.waiting_for_ticker)
    await call.answer()

async def show_price_for_coin(target: Message | CallbackQuery, coin_id: str, deps: Deps):
    """Универсальная функция для получения и отображения цены."""
    if isinstance(target, CallbackQuery):
        message = target.message
        await target.answer(f"⏳ Получаю курс для {coin_id.upper()}...")
    else:
        message = await target.answer("⏳ Ищу монету и получаю курс...")

    coin = await deps.coin_list_service.find_coin_by_query(coin_id)
    if not coin:
        await message.edit_text(f"❌ Не удалось найти информацию по '{coin_id}'.", reply_markup=get_back_to_main_menu_keyboard())
        return

    prices = await deps.price_service.get_prices([coin.id])
    price_value = prices.get(coin.id)
    
    if price_value is not None:
        response_text = format_price_info(coin, {"price": price_value})
        await message.edit_text(response_text, reply_markup=get_back_to_main_menu_keyboard())
    else:
        await message.edit_text(f"❌ Не удалось получить курс для {coin.name}.", reply_markup=get_back_to_main_menu_keyboard())

@router.callback_query(PriceCallback.filter(F.action == "show"))
async def handle_price_button_callback(call: CallbackQuery, callback_data: PriceCallback, state: FSMContext, deps: Deps):
    """Обрабатывает нажатие на кнопку с конкретной монетой."""
    await state.clear()
    await show_price_for_coin(call, callback_data.coin_id, deps)

@router.message(PriceInquiryState.waiting_for_ticker)
async def process_ticker_input_from_user(message: Message, state: FSMContext, deps: Deps):
    """Обрабатывает текстовый ввод тикера или названия от пользователя."""
    await state.clear()
    query = message.text.strip()
    await show_price_for_coin(message, query, deps)