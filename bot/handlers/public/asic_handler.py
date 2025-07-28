# ===============================================================
# Файл: bot/handlers/public/asic_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Обработчики для команд, связанных с ASIC-майнерами,
# включая топ, калькулятор и паспорт устройства.
# ===============================================================
import logging
from datetime import datetime, timezone
from typing import Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.services.asic_service import AsicService
from bot.services.user_service import UserService
from bot.states.asic_states import AsicExplorerStates
from bot.keyboards.asic_keyboards import get_top_asics_keyboard, get_asic_passport_keyboard
from bot.utils.models import AsicMiner

# --- ИСПРАВЛЕНИЕ: Импорт удален, так как функция будет локальной ---
# from bot.utils.formatters import format_asic_passport

logger = logging.getLogger(__name__)
router = Router(name="asic_handler")

# --- ЛОКАЛЬНАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---

def format_asic_passport(asic: AsicMiner, electricity_cost: float) -> str:
    """
    Формирует красивый текстовый паспорт для ASIC с расчетом чистой прибыли.
    Эта функция теперь является локальной для данного хэндлера.
    """
    power = asic.power or 0
    net_profit = asic.profitability

    # Считаем "грязную" прибыль, прибавляя обратно стоимость электричества
    power_kwh_per_day = (power / 1000) * 24
    daily_cost = power_kwh_per_day * electricity_cost
    gross_profit_from_net = net_profit + daily_cost

    specs_map = {
        "algorithm": "Алгоритм", "hashrate": "Хешрейт",
        "power": "Потребление", "efficiency": "Эффективность"
    }
    
    specs_list = []
    for key, rus_name in specs_map.items():
        value = getattr(asic, key, None)
        if value and value != "N/A":
            unit = " Вт" if key == "power" else ""
            specs_list.append(f" ▫️ <b>{rus_name}:</b> {value}{unit}")

    specs_text = "\n".join(specs_list)

    profit_text = (
        f" ▪️ <b>Доход (грязными):</b> ${gross_profit_from_net:.2f}/день\n"
        f" ▪️ <b>Доход (чистыми):</b> ${net_profit:.2f}/день\n"
        f"    (при цене э/э ${electricity_cost:.4f}/кВт·ч)"
    )

    return (
        f"📋 <b>Паспорт устройства: {asic.name}</b>\n\n"
        f"<b><u>Экономика:</u></b>\n{profit_text}\n\n"
        f"<b><u>Тех. характеристики:</u></b>\n{specs_text}\n"
    )

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ ---

async def show_top_asics_page(
    call: CallbackQuery,
    state: FSMContext,
    asic_service: AsicService,
    user_service: UserService
):
    """Отображает страницу с топом ASIC-майнеров."""
    user_id = call.from_user.id
    current_state = await state.get_data()
    page = current_state.get("page", 1)
    sort_by = current_state.get("sort_by", "profitability")

    electricity_cost = await user_service.get_user_electricity_cost(user_id)
    
    top_miners, last_update_time = await asic_service.get_top_asics(
        sort_by=sort_by,
        electricity_cost=electricity_cost
    )

    if not top_miners:
        await call.message.edit_text(
            "😕 Не удалось получить данные о майнерах. База данных пуста или источники недоступны. Попробуйте позже."
        )
        return

    now = datetime.now(timezone.utc)
    minutes_ago = int((now - last_update_time).total_seconds() / 60) if last_update_time else 0
    
    await call.message.edit_text(
        f"🏆 <b>Топ доходных ASIC</b> (сортировка: {sort_by})\n"
        f"<i>Данные обновлены {minutes_ago} минут назад.</i>",
        reply_markup=get_top_asics_keyboard(top_miners, page, sort_by)
    )

@router.callback_query(F.data.startswith("top_asics:"))
async def top_asics_navigator(
    call: CallbackQuery,
    state: FSMContext,
    asic_service: AsicService,
    user_service: UserService
):
    """Обрабатывает навигацию по меню топа ASIC."""
    await call.answer()
    action, value1, value2 = call.data.split(":")[1:]
    
    if action == "page":
        await state.update_data(page=int(value1), sort_by=value2)
    elif action == "sort":
        await state.update_data(page=1, sort_by=value1)

    await state.set_state(AsicExplorerStates.showing_top)
    await show_top_asics_page(call, state, asic_service, user_service)

@router.callback_query(F.data.startswith("asic_passport:"))
async def asic_passport_handler(
    call: CallbackQuery,
    state: FSMContext,
    asic_service: AsicService,
    user_service: UserService
):
    """Отображает паспорт ASIC-майнера."""
    await call.answer()
    asic_name = call.data.split(":", 1)[1]
    
    asic = await asic_service.find_asic_by_name(asic_name)
    if not asic:
        await call.answer("😕 Модель не найдена в базе.", show_alert=True)
        return
        
    electricity_cost = await user_service.get_user_electricity_cost(call.from_user.id)
    
    # Пересчитываем 'чистую' прибыльность для паспорта
    asic.profitability = AsicService.calculate_net_profit(
        asic.profitability, asic.power or 0, electricity_cost
    )

    text = format_asic_passport(asic, electricity_cost)
    await call.message.edit_text(
        text,
        reply_markup=get_asic_passport_keyboard(page=1, sort_by="profitability")
    )
