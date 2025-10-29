# src/bot/handlers/public/asic_handler.py
import logging
from datetime import datetime, timezone
from typing import Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.utils.dependencies import Deps
from bot.states.asic_states import AsicExplorerStates
from bot.keyboards.callback_factories import MenuCallback, AsicCallback
from bot.keyboards.asic_keyboards import get_top_asics_keyboard, get_asic_passport_keyboard
from bot.utils.formatters import format_asic_passport
from bot.utils.ui_helpers import edit_or_send_message

logger = logging.getLogger(__name__)
router = Router(name="asic_handler")


async def show_top_asics_page(update: Union[Message, CallbackQuery], state: FSMContext, deps: Deps):
    """Отображает страницу с топом ASIC-майнеров."""
    await edit_or_send_message(update, "⏳ Загружаю актуальный список ASIC...")

    await state.set_state(AsicExplorerStates.showing_top)

    fsm_data = await state.get_data()
    page = fsm_data.get("page", 1)

    user_profile, _ = await deps.user_service.get_or_create_user(update.from_user)
    electricity_cost = user_profile.electricity_cost

    try:
        top_miners, last_update_time = await deps.asic_service.get_top_asics(electricity_cost)
    except Exception as e:
        logger.exception(f"Error getting top ASICs: {e}")
        error_text = "😕 Произошла ошибка при загрузке данных. Попробуйте позже."
        await edit_or_send_message(update, error_text)
        return

    if not top_miners:
        error_text = "😕 Не удалось получить данные о майнерах. База данных пуста или источники недоступны. Попробуйте позже."
        await edit_or_send_message(update, error_text)
        return

    minutes_ago_str = "N/A"
    if last_update_time:
        minutes_ago = int((datetime.now(timezone.utc) - last_update_time).total_seconds() / 60)
        minutes_ago_str = str(minutes_ago)

    text = (f"🏆 <b>Топ доходных ASIC</b>\n"
            f"<i>Ваша цена э/э: ${electricity_cost:.4f}/кВт·ч. Обновлено {minutes_ago_str} мин. назад.</i>")

    keyboard = get_top_asics_keyboard(top_miners, page)
    await edit_or_send_message(update, text, keyboard)


@router.callback_query(MenuCallback.filter(F.action == "asics"))
async def top_asics_start(call: CallbackQuery, state: FSMContext, deps: Deps):
    """Входная точка для просмотра топа ASIC из главного меню."""
    await call.answer()
    await state.set_state(AsicExplorerStates.showing_top)
    await state.update_data(page=1)
    await show_top_asics_page(call, state, deps)


@router.callback_query(AsicCallback.filter(F.action == "page"), AsicExplorerStates.showing_top)
async def top_asics_paginator(call: CallbackQuery, state: FSMContext, deps: Deps, callback_data: AsicCallback):
    """Обрабатывает пагинацию и возврат к списку ASIC."""
    await call.answer()
    page = callback_data.page if callback_data.page is not None else 1
    await state.update_data(page=page)
    await show_top_asics_page(call, state, deps)


@router.callback_query(AsicCallback.filter(F.action == "passport"), AsicExplorerStates.showing_top)
async def asic_passport_handler(call: CallbackQuery, state: FSMContext, deps: Deps, callback_data: AsicCallback):
    """Отображает паспорт ASIC-майнера."""
    await call.answer()
    normalized_name = callback_data.asic_id

    if not normalized_name:
        logger.warning("Получен passport callback без asic_id.")
        return

    fsm_data = await state.get_data()
    page = fsm_data.get("page", 1)

    user_profile, _ = await deps.user_service.get_or_create_user(call.from_user)
    
    try:
        asic = await deps.asic_service.find_asic_by_normalized_name(normalized_name, user_profile.electricity_cost)
    except Exception as e:
        logger.exception(f"Error finding ASIC by name {normalized_name}: {e}")
        await call.answer("😕 Произошла ошибка при загрузке данных.", show_alert=True)
        return

    if not asic:
        await call.answer("😕 Модель не найдена в базе.", show_alert=True)
        return

    await state.set_state(AsicExplorerStates.showing_passport)
    text = format_asic_passport(asic, user_profile.electricity_cost)
    
    try:
        await call.message.edit_text(text, reply_markup=get_asic_passport_keyboard(page))
    except Exception as e:
        logger.exception(f"Error editing message with ASIC passport: {e}")
        await call.answer("😕 Не удалось отобразить паспорт майнера.", show_alert=True)


@router.callback_query(AsicCallback.filter(F.action == "set_cost"), AsicExplorerStates.showing_top)
async def prompt_for_electricity_cost(call: CallbackQuery, state: FSMContext):
    """Запрашивает у пользователя стоимость электроэнергии."""
    await state.set_state(AsicExplorerStates.prompt_electricity_cost)
    await call.answer()
    
    try:
        await call.message.edit_text(
            "💡 <b>Введите стоимость 1 кВт·ч в USD.</b>\n\n"
            "Например: <code>0.05</code> (это 5 центов). "
            "Эта цена будет сохранена в вашем профиле для всех будущих расчетов.",
            reply_markup=None
        )
    except Exception as e:
        logger.exception(f"Error prompting for electricity cost: {e}")


@router.message(AsicExplorerStates.prompt_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, deps: Deps):
    """Обрабатывает введенную стоимость и обновляет список."""
    try:
        cost_str = message.text.replace(',', '.').strip()
        cost = float(cost_str)
        if not (0 <= cost < 1):
            raise ValueError("Cost must be a positive number less than 1.")
    except (ValueError, TypeError):
        await message.reply("❌ <b>Ошибка.</b> Введите корректное число, например: <code>0.05</code>")
        return

    try:
        user = await deps.user_service.get_user(message.from_user.id)
        if user:
            user.electricity_cost = cost
            await deps.user_service.save_user(user)

        await message.answer(f"✅ Ваша цена электроэнергии <b>${cost:.4f}/кВт·ч</b> сохранена! Пересчитываю топ...")
        await show_top_asics_page(message, state, deps)
    except Exception as e:
        logger.exception(f"Error processing electricity cost: {e}")
        await message.answer("❌ Произошла ошибка при сохранении. Попробуйте позже.")