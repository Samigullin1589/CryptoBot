# ===============================================================
# Файл: bot/handlers/tools/calculator_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - РЕФАКТОРИНГ)
# Описание: "Тонкий" обработчик для "Калькулятора доходности".
# ИСПРАВЛЕНИЕ: Добавлен фильтр MenuCallback для прямого отклика на кнопку меню.
# ===============================================================
import logging
from typing import Union
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states.mining_states import CalculatorStates
from bot.keyboards.mining_keyboards import (
    get_calculator_cancel_keyboard, get_currency_selection_keyboard,
    get_asic_selection_keyboard, get_calculator_result_keyboard
)
from bot.keyboards.callback_factories import MenuCallback
from bot.utils.dependencies import Deps
from bot.utils.models import AsicMiner, CalculationInput
from bot.utils.formatters import format_calculation_result

calculator_router = Router(name=__name__)
logger = logging.getLogger(__name__)

@calculator_router.callback_query(MenuCallback.filter(F.action == "calculator"))
async def start_profit_calculator(call: CallbackQuery, state: FSMContext, deps: Deps, **kwargs):
    """Запускает сценарий калькулятора доходности из главного меню."""
    await state.clear()
    await deps.admin_service.track_action(call.from_user.id, "nav:calculator")
    
    text = "Выберите валюту, в которой вы укажете стоимость электроэнергии:"
    keyboard = get_currency_selection_keyboard()
    
    await call.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(CalculatorStates.waiting_for_currency)
    await call.answer()

@calculator_router.callback_query(F.data == "calc_action:cancel")
async def cancel_calculator(call: CallbackQuery, state: FSMContext):
    """Отменяет сценарий калькулятора в любом состоянии."""
    current_state = await state.get_state()
    if current_state is None:
        return await call.answer()
    await state.clear()
    await call.message.edit_text("✅ Расчет отменен.")
    await call.answer()

@calculator_router.callback_query(F.data.startswith("calc_currency:"), CalculatorStates.waiting_for_currency)
async def process_currency_selection(call: CallbackQuery, state: FSMContext):
    await call.answer()
    currency = call.data.split(":")[1]
    await state.update_data(currency=currency)
    
    prompt_text = (
        "💡 Введите стоимость электроэнергии в <b>USD</b> за кВт/ч (например, <code>0.05</code>):"
        if currency == "usd" else
        "💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч (например, <code>4.5</code>):"
    )
    
    await call.message.edit_text(prompt_text, reply_markup=get_calculator_cancel_keyboard())
    await state.set_state(CalculatorStates.waiting_for_electricity_cost)

@calculator_router.message(CalculatorStates.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, deps: Deps):
    try:
        cost = float(message.text.replace(',', '.').strip())
        if cost < 0: raise ValueError
    except (ValueError, TypeError):
        await message.answer("Пожалуйста, введите корректное число (например, <b>0.05</b> или <b>4.5</b>).")
        return

    msg = await message.answer("⏳ Обрабатываю...")
    user_data = await state.get_data()
    
    cost_usd = cost
    if user_data.get("currency") == "rub":
        rate_usd_rub = 95.0 # Заглушка, можно заменить на вызов API
        cost_usd = cost / rate_usd_rub
    
    await msg.edit_text("⏳ Загружаю список оборудования...")
    all_asics, _ = await deps.asic_service.get_top_asics(0.05, count=1000)
    
    if not all_asics:
        await msg.edit_text("❌ Ошибка: не удалось загрузить список ASIC.", reply_markup=get_calculator_cancel_keyboard())
        return

    await state.update_data(
        electricity_cost_usd=cost_usd,
        asic_list_json=[asic.model_dump() for asic in all_asics]
    )
    
    keyboard = get_asic_selection_keyboard(all_asics, page=0)
    await msg.edit_text("✅ Отлично! Теперь выберите ваш ASIC-майнер из списка:", reply_markup=keyboard)
    await state.set_state(CalculatorStates.waiting_for_asic_selection)

@calculator_router.callback_query(F.data.startswith("calc_page:"), CalculatorStates.waiting_for_asic_selection)
async def process_asic_pagination(call: CallbackQuery, state: FSMContext):
    await call.answer()
    page = int(call.data.split(":")[1])
    user_data = await state.get_data()
    asic_list = [AsicMiner(**data) for data in user_data.get("asic_list_json", [])]
    
    keyboard = get_asic_selection_keyboard(asic_list, page=page)
    await call.message.edit_text("Выберите ваш ASIC-майнер из списка:", reply_markup=keyboard)

@calculator_router.callback_query(F.data.startswith("calc_select_asic:"), CalculatorStates.waiting_for_asic_selection)
async def process_asic_selection_item(call: CallbackQuery, state: FSMContext):
    await call.answer()
    asic_index = int(call.data.split(":")[1])
    user_data = await state.get_data()
    asic_list = [AsicMiner(**data) for data in user_data.get("asic_list_json", [])]

    if asic_index >= len(asic_list):
        return await call.answer("❌ Ошибка выбора. Список мог обновиться.", show_alert=True)
        
    await state.update_data(selected_asic_json=asic_list[asic_index].model_dump())
    
    await call.message.edit_text(
        "📊 Введите комиссию вашего пула в % (например, <code>1</code>):",
        reply_markup=get_calculator_cancel_keyboard()
    )
    await state.set_state(CalculatorStates.waiting_for_pool_commission)

@calculator_router.message(CalculatorStates.waiting_for_pool_commission)
async def process_pool_commission(message: Message, state: FSMContext, deps: Deps):
    try:
        commission_percent = float(message.text.replace(',', '.').strip())
        if not (0 <= commission_percent < 100): raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат комиссии. Введите число (например, <code>1.5</code>).")
        return

    msg = await message.answer("⏳ Собираю данные и считаю...")
    user_data = await state.get_data()
    
    selected_asic = AsicMiner(**user_data["selected_asic_json"])
    
    calc_input = CalculationInput(
        hashrate_str=selected_asic.hashrate,
        power_consumption_watts=selected_asic.power,
        electricity_cost=user_data["electricity_cost_usd"],
        pool_commission=commission_percent
    )
    
    result = await deps.mining_service.calculate_btc_profitability(calc_input)
    
    if not result:
         await msg.edit_text("❌ Не удалось получить данные для расчета. Попробуйте позже.")
         await state.clear()
         return

    result_text = format_calculation_result(result)
    await msg.edit_text(result_text, reply_markup=get_calculator_result_keyboard(), disable_web_page_preview=True)
    await state.clear()