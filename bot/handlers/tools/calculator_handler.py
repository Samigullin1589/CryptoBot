# ===============================================================
# Файл: bot/handlers/tools/calculator_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчики для Калькулятора доходности.
# Управляет FSM и делегирует логику в сервисы.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.states.mining_states import ProfitCalculatorStates
from bot.keyboards.mining_keyboards import *
from bot.services.mining_service import MiningService
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id
from bot.utils.models import AsicMiner

router = Router()
logger = logging.getLogger(__name__)

# --- Точка входа и отмена ---
@router.callback_query(F.data == "menu_calculator")
@router.message(F.text == "⛏️ Калькулятор")
async def start_calculator(update: Union[Message, CallbackQuery], state: FSMContext, admin_service: AdminService):
    """Точка входа в калькулятор."""
    await admin_service.track_command_usage("⛏️ Калькулятор")
    await state.clear()
    
    message, _ = await get_message_and_chat_id(update)
    await message.answer(
        "Выберите валюту для указания стоимости электроэнергии:",
        reply_markup=get_calculator_currency_keyboard().as_markup()
    )
    await state.set_state(ProfitCalculatorStates.waiting_for_currency)
    if isinstance(update, CallbackQuery):
        await update.answer()

@router.callback_query(F.data == "calc_action:cancel")
async def cancel_calculator(call: CallbackQuery, state: FSMContext):
    """Отменяет сценарий калькулятора."""
    await state.clear()
    await call.message.edit_text("✅ Расчет отменен.")
    await call.answer()

# --- Шаги FSM ---
@router.callback_query(ProfitCalculatorStates.waiting_for_currency, F.data.startswith("calc_action:set_currency:"))
async def process_currency_selection(call: CallbackQuery, state: FSMContext):
    """Шаг 1: Обработка выбора валюты."""
    await call.answer()
    currency = call.data.split(":")[-1]
    await state.update_data(currency=currency)
    
    prompt_text = "💡 Введите стоимость электроэнергии в <b>USD</b> за кВт/ч (например, <code>0.05</code>):"
    if currency == "rub":
        prompt_text = "💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч (например, <code>4.5</code>):"
        
    await call.message.edit_text(prompt_text, reply_markup=get_calculator_cancel_keyboard().as_markup())
    await state.set_state(ProfitCalculatorStates.waiting_for_electricity_cost)

@router.message(ProfitCalculatorStates.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, mining_service: MiningService):
    """Шаг 2: Обработка ввода стоимости э/э и показ списка ASIC."""
    try:
        cost = float(message.text.replace(',', '.').strip())
        if cost < 0: raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число (например, <b>0.05</b>).")
        return

    msg = await message.answer("⏳ Конвертирую валюту и загружаю оборудование...")
    
    success, result = await mining_service.prepare_asic_list_for_calculator(
        cost_input=cost,
        currency=(await state.get_data()).get("currency")
    )
    
    if not success:
        await msg.edit_text(f"❌ {result}", reply_markup=get_calculator_cancel_keyboard().as_markup())
        return
        
    await state.update_data(electricity_cost_usd=result['cost_usd'], asic_list=result['asics'])
    
    keyboard = get_calculator_asic_keyboard([AsicMiner(**data) for data in result['asics']], page=0)
    await msg.edit_text("✅ Отлично! Теперь выберите ваш ASIC-майнер:", reply_markup=keyboard.as_markup())
    await state.set_state(ProfitCalculatorStates.waiting_for_asic_selection)

@router.callback_query(ProfitCalculatorStates.waiting_for_asic_selection, F.data.startswith("calc_nav:page:"))
async def process_asic_pagination(call: CallbackQuery, state: FSMContext):
    """Шаг 2.1: Пагинация по списку ASIC."""
    await call.answer()
    page = int(call.data.split(":")[-1])
    user_data = await state.get_data()
    asic_list = [AsicMiner(**data) for data in user_data.get("asic_list", [])]
    keyboard = get_calculator_asic_keyboard(asic_list, page=page)
    await call.message.edit_reply_markup(reply_markup=keyboard.as_markup())

@router.callback_query(ProfitCalculatorStates.waiting_for_asic_selection, F.data == "calc_action:invalid_asic")
async def process_invalid_asic_selection(call: CallbackQuery):
    """Шаг 2.2: Сообщение о невалидном ASIC."""
    await call.answer("ℹ️ Для этой модели нет данных для расчета.", show_alert=True)

@router.callback_query(ProfitCalculatorStates.waiting_for_asic_selection, F.data.startswith("calc_action:select_asic:"))
async def process_asic_selection(call: CallbackQuery, state: FSMContext):
    """Шаг 3: Обработка выбора ASIC и запрос комиссии пула."""
    await call.answer()
    asic_index = int(call.data.split(":")[-1])
    await state.update_data(selected_asic_index=asic_index)
    
    await call.message.edit_text(
        "📊 Введите комиссию вашего пула в % (например, <code>1</code> или <code>1.5</code>):",
        reply_markup=get_calculator_cancel_keyboard().as_markup()
    )
    await state.set_state(ProfitCalculatorStates.waiting_for_pool_commission)

@router.message(ProfitCalculatorStates.waiting_for_pool_commission)
async def process_pool_commission(message: Message, state: FSMContext, mining_service: MiningService):
    """Шаг 4: Обработка комиссии и финальный расчет."""
    try:
        commission = float(message.text.replace(',', '.').strip())
        if not (0 <= commission < 100): raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 99.9.")
        return

    msg = await message.answer("⏳ Считаю...")
    user_data = await state.get_data()
    
    result_text = await mining_service.get_calculator_result(
        user_data=user_data,
        pool_commission=commission
    )
    
    await msg.edit_text(result_text, disable_web_page_preview=True)
    await state.clear()
