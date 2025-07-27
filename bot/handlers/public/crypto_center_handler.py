# ===============================================================
# Файл: bot/handlers/public/crypto_center_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный хэндлер для Крипто-Центра.
# Использует FSM, сервисы и отдельные модули для клавиатур и
# форматирования. Поддерживает пагинацию.
# ===============================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.services.crypto_center_service import CryptoCenterService
from bot.services.admin_service import AdminService
from bot.states.crypto_center_states import CryptoCenterStates
from bot.keyboards.crypto_center_keyboards import *
from bot.utils.formatters import *
from bot.texts.public_texts import CRYPTO_CENTER_TEXTS

router = Router()
logger = logging.getLogger(__name__)

# --- Точка входа и навигация ---

@router.callback_query(F.data == "menu_crypto_center")
async def crypto_center_entry(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """Точка входа в Крипто-Центр."""
    await admin_service.track_command_usage("💎 Крипто-Центр")
    await state.set_state(CryptoCenterStates.main_menu)
    await call.message.edit_text(
        CRYPTO_CENTER_TEXTS['main_menu'],
        reply_markup=get_crypto_center_main_menu_keyboard()
    )
    await call.answer()

@router.callback_query(F.data.startswith("cc_nav:"))
async def crypto_center_navigation(call: CallbackQuery, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Единый обработчик для навигации по меню Крипто-Центра."""
    await call.answer()
    nav_path = call.data.split(":")[1:]
    action = nav_path[0]
    
    # --- Главное меню ---
    if action == "main_menu":
        await state.set_state(CryptoCenterStates.main_menu)
        await call.message.edit_text(
            CRYPTO_CENTER_TEXTS['main_menu'],
            reply_markup=get_crypto_center_main_menu_keyboard()
        )
        
    # --- Меню гайдов ---
    elif action == "guides_menu":
        await state.set_state(CryptoCenterStates.viewing_guides_menu)
        await call.message.edit_text(
            CRYPTO_CENTER_TEXTS['guides_menu'],
            reply_markup=get_crypto_center_guides_menu_keyboard()
        )
        
    # --- Лента новостей ---
    elif action == "feed":
        await state.set_state(CryptoCenterStates.viewing_feed)
        await call.message.edit_text("⏳ AI анализирует свежие новости...")
        feed_items = await crypto_center_service.fetch_live_feed_with_summary()
        text = format_crypto_feed(feed_items)
        await call.message.edit_text(text, reply_markup=get_live_feed_keyboard(), disable_web_page_preview=True)
        
    # --- Список Airdrop'ов (с пагинацией) ---
    elif action == "airdrops_list":
        page = int(nav_path[1]) if len(nav_path) > 1 else 1
        await state.set_state(CryptoCenterStates.viewing_airdrops_list)
        await call.message.edit_text("⏳ AI ищет Airdrop-возможности...")
        
        airdrops, total_pages = await crypto_center_service.get_airdrops_paginated(call.from_user.id, page)
        
        if not airdrops:
            await call.message.edit_text(
                "😕 AI не нашел актуальных Airdrop-возможностей.",
                reply_markup=get_back_to_cc_menu_keyboard('guides_menu')
            )
            return
            
        await call.message.edit_text(
            CRYPTO_CENTER_TEXTS['airdrops_list'],
            reply_markup=get_airdrops_list_keyboard(airdrops, page, total_pages)
        )
        
    # --- Майнинг-сигналы ---
    elif action == "mining_signals":
        await state.set_state(CryptoCenterStates.viewing_mining_signals)
        await call.message.edit_text("⏳ AI анализирует майнинг-сигналы...")
        signals = await crypto_center_service.generate_mining_alpha()
        text = format_mining_signals(signals)
        await call.message.edit_text(text, reply_markup=get_back_to_cc_menu_keyboard('guides_menu'), disable_web_page_preview=True)

# --- Обработка действий пользователя ---

@router.callback_query(F.data.startswith("cc_action:"))
async def crypto_center_actions(call: CallbackQuery, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Единый обработчик для действий (например, отметить задачу)."""
    action_path = call.data.split(":")[1:]
    action = action_path[0]
    
    # --- Показ деталей Airdrop'а ---
    if action == "show_airdrop":
        airdrop_id = action_path[1]
        await state.update_data(current_airdrop_id=airdrop_id)
        await state.set_state(CryptoCenterStates.viewing_airdrop_details)
        
        airdrop = await crypto_center_service.get_airdrop_by_id(airdrop_id)
        if not airdrop:
            await call.answer("❌ Проект не найден. Возможно, он уже не актуален.", show_alert=True)
            return
            
        user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id)
        text = format_airdrop_details(airdrop)
        keyboard = get_airdrop_details_keyboard(airdrop, user_progress)
        await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)

    # --- Отметить/снять задачу в чеклисте ---
    elif action == "toggle_task":
        try:
            airdrop_id, task_index_str = action_path[1], action_path[2]
            task_index = int(task_index_str)
        except (IndexError, ValueError):
            await call.answer("❌ Ошибка данных.", show_alert=True)
            return
            
        await crypto_center_service.toggle_task_status(call.from_user.id, airdrop_id, task_index)
        
        # Обновляем клавиатуру без перерисовки всего сообщения
        airdrop = await crypto_center_service.get_airdrop_by_id(airdrop_id)
        user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id)
        new_keyboard = get_airdrop_details_keyboard(airdrop, user_progress)
        
        try:
            await call.message.edit_reply_markup(reply_markup=new_keyboard)
            await call.answer("Статус задачи обновлен!")
        except TelegramBadRequest as e:
            logger.warning(f"Could not edit reply markup for toggle_task: {e}")
            await call.answer("Статус обновлен, но не удалось обновить кнопки.")
