# ===============================================================
# Файл: bot/handlers/public/asic_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Переработанный хэндлер для команд, связанных с ASIC.
# Использует FSM, сервисы и отдельные модули для клавиатур и
# форматирования. Поддерживает пагинацию и сортировку.
# ===============================================================
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.config.settings import settings
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.user_service import UserService
from bot.keyboards.asic_keyboards import get_top_asics_keyboard, get_electricity_tariff_keyboard
from bot.states.asic_states import AsicExplorerStates
from bot.utils.formatters import format_asic_passport

router = Router()
logger = logging.getLogger(__name__)

# --- Хэндлер для команды /top_asics и пагинации ---

async def show_top_asics_page(
    message: Message,
    asic_service: AsicService,
    user_service: UserService,
    state: FSMContext,
    page: int = 1,
    sort_by: str = "profitability"
):
    """Общая логика для отображения страницы с топом ASIC."""
    await state.set_state(AsicExplorerStates.viewing_top_list)
    
    electricity_cost = await user_service.get_user_electricity_cost(message.from_user.id)
    
    top_miners, total_pages, last_update_time = await asic_service.get_top_asics_paginated(
        page=page,
        page_size=7, # Оптимальное количество для одного экрана
        sort_by=sort_by,
        electricity_cost=electricity_cost
    )

    if not top_miners:
        await message.edit_text("😕 Не удалось получить данные о майнерах. База данных пуста или источники недоступны. Попробуйте позже.")
        return

    sort_text = "чистой доходности" if sort_by == "profitability" else "энергоэффективности"
    response_lines = [f"🏆 <b>Топ ASIC по {sort_text}</b> (при цене э/э ${electricity_cost:.4f}/кВт·ч)\n"]
    
    for i, miner in enumerate(top_miners, (page - 1) * 7 + 1):
        profit_or_eff = f"${miner.profitability:.2f}/д" if sort_by == "profitability" else f"{miner.efficiency} J/TH"
        line = f"{i}. <b>{miner.name}</b>\n   <code>{profit_or_eff} | {miner.algorithm}</code>"
        response_lines.append(line)
    
    if last_update_time:
        minutes_ago = int((datetime.now(timezone.utc) - last_update_time).total_seconds() / 60)
        response_lines.append(f"\n<i>Данные обновлены {minutes_ago} мин. назад.</i>")

    await message.edit_text(
        "\n".join(response_lines),
        reply_markup=get_top_asics_keyboard(page, total_pages, sort_by),
        disable_web_page_preview=True
    )

@router.message(Command("top_asics"))
async def top_asics_command_handler(
    message: Message, asic_service: AsicService, user_service: UserService, admin_service: AdminService, state: FSMContext
):
    """Обрабатывает первоначальный вызов команды /top_asics."""
    await admin_service.track_command_usage("/top_asics")
    msg = await message.answer("🔍 Собираю данные... Это может занять несколько секунд.")
    await show_top_asics_page(msg, asic_service, user_service, state)

@router.callback_query(F.data.startswith("top_asics:page:"))
async def top_asics_callback_handler(
    call: CallbackQuery, asic_service: AsicService, user_service: UserService, state: FSMContext
):
    """Обрабатывает нажатия на кнопки пагинации и сортировки."""
    await call.answer()
    _, _, page_str, sort_by = call.data.split(":")
    await show_top_asics_page(call.message, asic_service, user_service, state, int(page_str), sort_by)

# --- Хэндлер для команды /asic [модель] ---

@router.message(Command("asic"))
async def asic_passport_handler(
    message: Message, asic_service: AsicService, user_service: UserService, admin_service: AdminService, state: FSMContext
):
    """Обрабатывает команду /asic [модель] и выдает паспорт устройства."""
    await admin_service.track_command_usage("/asic")
    await state.set_state(AsicExplorerStates.viewing_passport)
    
    try:
        model_query = message.text.split(maxsplit=1)[1]
    except IndexError:
        await message.reply("Пожалуйста, укажите модель ASIC. Например: <code>/asic s19k pro</code>")
        return

    found_asic_dict = await asic_service.find_asic_by_query(model_query)
        
    if found_asic_dict:
        electricity_cost = await user_service.get_user_electricity_cost(message.from_user.id)
        response_text = format_asic_passport(found_asic_dict, electricity_cost)
        await message.answer(response_text, disable_web_page_preview=True)
    else:
        await message.answer(f"😕 Модель, похожая на '<code>{model_query}</code>', не найдена.")

# --- Хэндлеры для установки тарифа на электроэнергию ---

@router.message(Command("set_cost"))
async def set_electricity_cost_handler(message: Message, state: FSMContext, admin_service: AdminService):
    """Отправляет пользователю инлайн-клавиатуру для выбора тарифа."""
    await admin_service.track_command_usage("/set_cost")
    await state.set_state(AsicExplorerStates.setting_cost)
    
    await message.answer(
        "Выберите ваш тариф на электроэнергию. Это повлияет на расчет чистой доходности.",
        reply_markup=get_electricity_tariff_keyboard(settings.game.ELECTRICITY_TARIFFS)
    )

@router.callback_query(F.data.startswith("set_tariff:"), AsicExplorerStates.setting_cost)
async def process_tariff_selection(callback: CallbackQuery, user_service: UserService, state: FSMContext):
    """Обрабатывает выбор тарифа пользователем."""
    await state.clear()
    try:
        tariff_name = callback.data.split(":")[1]
    except IndexError:
        await callback.answer("Ошибка! Не удалось определить тариф.", show_alert=True)
        return

    tariff_info = settings.game.ELECTRICITY_TARIFFS.get(tariff_name)
    if not tariff_info:
        await callback.answer("Ошибка! Такой тариф не найден.", show_alert=True)
        return

    cost = tariff_info["cost_per_hour"]
    await user_service.set_user_electricity_cost(callback.from_user.id, cost)
    
    await callback.message.edit_text(
        f"✅ Ваш тариф изменен на '<b>{tariff_name}</b>'.\n"
        f"Новая стоимость для расчетов: <b>${cost:.4f}/кВт·ч</b>."
    )
    await callback.answer("Настройки сохранены!")
