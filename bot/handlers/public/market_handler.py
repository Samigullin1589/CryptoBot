# =================================================================================
# Файл: bot/handlers/public/market_handler.py (ВЕРСЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНАЯ)
# Описание: Обработчики команд и callback'ов для взаимодействия с рынком.
# ИСПРАВЛЕНИЕ: Полный переход на использование MarketCallback factory.
# =================================================================================

import logging
from math import ceil
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.services.market_service import AsicMarketService
from bot.services.mining_game_service import MiningGameService
from bot.keyboards.market_keyboards import (
    get_market_listings_keyboard, 
    get_choose_asic_to_sell_keyboard
)
from bot.keyboards.callback_factories import MarketCallback
from bot.states.market_states import MarketStates
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)
router = Router()
PAGE_SIZE = 5  # Количество лотов на одной странице

# --- Обработчик команды /market и постраничной навигации ---

@router.message(Command("market"))
@router.callback_query(MarketCallback.filter(F.action == "page"))
async def market_start_handler(message: types.Message | types.CallbackQuery, market_service: AsicMarketService, state: FSMContext, callback_data: MarketCallback = None):
    await state.clear() # Сбрасываем любое состояние, если пользователь зашел на рынок
    
    page = callback_data.page if callback_data else 0
    
    if isinstance(message, types.CallbackQuery):
        target_message = message.message
    else:
        target_message = message

    all_listings = await market_service.get_market_listings(offset=0, count=1000)
    total_pages = ceil(len(all_listings) / PAGE_SIZE)
    
    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    current_page_listings = all_listings[start_index:end_index]

    text = "🛒 <b>Рынок оборудования</b>\n\nЗдесь вы можете купить оборудование у других игроков."
    if not current_page_listings:
        text += "\n\nНа данный момент на рынке нет доступных лотов."

    keyboard = get_market_listings_keyboard(current_page_listings, page, total_pages)

    if isinstance(message, types.CallbackQuery):
        await target_message.edit_text(text, reply_markup=keyboard)
        await message.answer()
    else:
        await target_message.answer(text, reply_markup=keyboard)

# --- Сценарий Продажи Оборудования (FSM) ---

@router.callback_query(MarketCallback.filter(F.action == "sell_start"))
async def sell_start_handler(callback: types.CallbackQuery, state: FSMContext, mining_game_service: MiningGameService):
    user_id = callback.from_user.id
    hangar_key = mining_game_service.keys.user_hangar(user_id)
    user_asics_json = await mining_game_service.redis.hvals(hangar_key)
    user_asics = [AsicMiner.model_validate_json(asic_json) for asic_json in user_asics_json]

    if not user_asics:
        await callback.answer("❌ В вашем ангаре нет оборудования для продажи.", show_alert=True)
        return

    await state.set_state(MarketStates.choosing_asic_to_sell)
    keyboard = get_choose_asic_to_sell_keyboard(user_asics)
    await callback.message.edit_text("👇 Выберите оборудование, которое хотите выставить на продажу:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(MarketStates.choosing_asic_to_sell, MarketCallback.filter(F.action == "sell_select"))
async def sell_select_asic_handler(callback: types.CallbackQuery, state: FSMContext, callback_data: MarketCallback):
    asic_id = callback_data.asic_id
    await state.update_data(asic_id_to_sell=asic_id)
    await state.set_state(MarketStates.entering_price)
    
    await callback.message.edit_text("💰 Теперь введите цену продажи в монетах (например: 1500.50).")
    await callback.answer()

@router.message(MarketStates.entering_price)
async def sell_enter_price_handler(message: types.Message, state: FSMContext, market_service: AsicMarketService):
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите положительное число (например: 1500 или 1500.5).")
        return

    data = await state.get_data()
    asic_id = data.get("asic_id_to_sell")
    
    listing_id = await market_service.list_asic_for_sale(message.from_user.id, asic_id, price)
    
    if listing_id:
        await message.answer(f"✅ Ваше оборудование успешно выставлено на продажу по цене {price:,.2f} монет!")
    else:
        await message.answer("❌ Произошла ошибка при выставлении лота. Возможно, оборудование уже используется.")

    await state.clear()
    # После завершения сценария, показываем обновленный рынок
    await market_start_handler(message, market_service, state)

# --- Обработчик Покупки ---

@router.callback_query(MarketCallback.filter(F.action == "buy"))
async def buy_item_handler(callback: types.CallbackQuery, market_service: AsicMarketService, state: FSMContext, callback_data: MarketCallback):
    listing_id = callback_data.listing_id
    
    result_text = await market_service.buy_asic(callback.from_user.id, listing_id)
    
    await callback.answer(result_text, show_alert=True)
    
    # Обновляем сообщение с рынком, чтобы купленный лот исчез
    await market_start_handler(callback, market_service, state)

# --- Обработчик отмены FSM ---
@router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm_handler(callback: types.CallbackQuery, state: FSMContext, market_service: AsicMarketService):
    await state.clear()
    await callback.answer("Действие отменено.", show_alert=True)
    # Возвращаем пользователя на главную страницу рынка
    await market_start_handler(callback, market_service, state)