# ===============================================================
# Файл: bot/handlers/tools/calculator_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: "Тонкий" обработчик для "Калькулятора доходности".
# Управляет сложным сценарием FSM и делегирует всю логику
# вычислений в сервисы.
# ===============================================================
import logging
from typing import Union
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.services.asic_service import AsicService
from bot.services.admin_service import AdminService
from bot.services.mining_service import MiningService
from bot.services.market_data_service import MarketDataService
from bot.states.mining_states import CalculatorState
from bot.keyboards.mining_keyboards import (
    get_calculator_cancel_keyboard, get_currency_selection_keyboard,
    get_asic_selection_keyboard
)
from bot.utils.models import AsicMiner
from bot.utils.formatters import format_calculation_result

calculator_router = Router()
logger = logging.getLogger(__name__)

# --- Запуск и отмена калькулятора ---

@calculator_router.callback_query(F.data == "nav:calculator")
@calculator_router.message(F.text == "⛏️ Калькулятор")
async def start_profit_calculator(update: Union[Message, CallbackQuery], state: FSMContext, admin_service: AdminService):
    """Запускает сценарий калькулятора доходности."""
    await state.clear()
    await admin_service.track_action("nav:calculator")
    
    text = "Выберите валюту, в которой вы укажете стоимость электроэнергии:"
    keyboard = get_currency_selection_keyboard()
    
    message = update.message if isinstance(update, CallbackQuery) else update
    await message.answer(text, reply_markup=keyboard)
    
    await state.set_state(CalculatorState.waiting_for_currency)

@calculator_router.callback_query(CalculatorState, F.data == "calc_action:cancel")
async def cancel_calculator(call: CallbackQuery, state: FSMContext):
    """Отменяет сценарий калькулятора."""
    await state.clear()
    await call.message.edit_text("✅ Расчет отменен.")
    await call.answer()

# --- Шаги сценария FSM ---

@calculator_router.callback_query(CalculatorState.waiting_for_currency, F.data.startswith("calc_currency:"))
async def process_currency_selection(call: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор валюты."""
    currency = call.data.split(":")[1]
    await state.update_data(currency=currency)
    
    prompt_text = (
        "💡 Введите стоимость электроэнергии в <b>USD</b> за кВт/ч (например, <code>0.05</code>):"
        if currency == "usd" else
        "💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч (например, <code>4.5</code>):"
    )
    
    await call.message.edit_text(prompt_text, reply_markup=get_calculator_cancel_keyboard())
    await state.set_state(CalculatorState.waiting_for_electricity_cost)

@calculator_router.message(CalculatorState.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, asic_service: AsicService, market_data_service: MarketDataService):
    """Обрабатывает ввод стоимости электроэнергии."""
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
        await msg.edit_text("⏳ Получаю актуальный курс USD/RUB...")
        rate_usd_rub = await market_data_service.get_usd_rub_rate()
        if not rate_usd_rub:
            await msg.edit_text("❌ Не удалось получить курс валют. Попробуйте позже.", reply_markup=get_calculator_cancel_keyboard())
            return
        cost_usd = cost / rate_usd_rub
    
    await msg.edit_text("⏳ Загружаю список оборудования...")
    all_asics, _ = await asic_service.get_top_asics(count=1000)
    
    if not all_asics:
        await msg.edit_text("❌ Ошибка: не удалось загрузить список ASIC.", reply_markup=get_calculator_cancel_keyboard())
        return

    await state.update_data(
        electricity_cost_usd=cost_usd,
        asic_list_json=[asic.model_dump() for asic in all_asics]
    )
    
    keyboard = get_asic_selection_keyboard(all_asics, page=0)
    await msg.edit_text("✅ Отлично! Теперь выберите ваш ASIC-майнер из списка:", reply_markup=keyboard)
    await state.set_state(CalculatorState.waiting_for_asic_selection)

@calculator_router.callback_query(CalculatorState.waiting_for_asic_selection, F.data.startswith("calc_page:"))
async def process_asic_pagination(call: CallbackQuery, state: FSMContext):
    """Обрабатывает пагинацию в списке ASIC."""
    page = int(call.data.split(":")[1])
    user_data = await state.get_data()
    asic_list = [AsicMiner(**data) for data in user_data.get("asic_list_json", [])]
    
    keyboard = get_asic_selection_keyboard(asic_list, page=page)
    await call.message.edit_text("Выберите ваш ASIC-майнер из списка:", reply_markup=keyboard)

@calculator_router.callback_query(CalculatorState.waiting_for_asic_selection, F.data.startswith("calc_select_asic:"))
async def process_asic_selection_item(call: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор ASIC из списка."""
    asic_index = int(call.data.split(":")[1])
    user_data = await state.get_data()
    asic_list = [AsicMiner(**data) for data in user_data.get("asic_list_json", [])]

    if asic_index >= len(asic_list):
        await call.answer("❌ Ошибка выбора. Список мог обновиться. Попробуйте снова.", show_alert=True)
        return
        
    await state.update_data(selected_asic_json=asic_list[asic_index].model_dump())
    
    await call.message.edit_text(
        "📊 Введите комиссию вашего пула в % (например, <code>1</code> или <code>1.5</code>):",
        reply_markup=get_calculator_cancel_keyboard()
    )
    await state.set_state(CalculatorState.waiting_for_pool_commission)

@calculator_router.message(CalculatorState.waiting_for_pool_commission)
async def process_pool_commission(message: Message, state: FSMContext, mining_service: MiningService, market_data_service: MarketDataService):
    """Обрабатывает ввод комиссии пула и выполняет финальный расчет."""
    try:
        commission_percent = float(message.text.replace(',', '.').strip())
        if not (0 <= commission_percent < 100): raise ValueError
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат комиссии. Введите число (например, <code>1.5</code>).")
        return

    msg = await message.answer("⏳ Собираю данные и считаю...")
    user_data = await state.get_data()
    
    selected_asic = AsicMiner(**user_data["selected_asic_json"])
    
    # Собираем все необходимые рыночные данные для расчета
    input_data = await market_data_service.get_data_for_calculation()
    if not input_data:
         await msg.edit_text("❌ Не удалось получить ключевые данные для расчета. Попробуйте позже.")
         await state.clear()
         return

    # Выполняем расчет
    result = await mining_service.calculate(
        asic=selected_asic,
        calculation_input=input_data,
        electricity_cost_usd=user_data["electricity_cost_usd"],
        pool_commission_percent=commission_percent
    )
    
    result_text = format_calculation_result(result)
    
    await msg.edit_text(result_text, disable_web_page_preview=True)
    await state.clear()
