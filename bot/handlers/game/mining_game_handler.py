# ===============================================================
# Файл: bot/handlers/game/mining_game_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчики для игры "Виртуальный Майнинг".
# Управляет навигацией и вызывает методы MiningGameService.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot.states.mining_states import MiningGameStates
from bot.keyboards.mining_keyboards import *
from bot.services.mining_service import MiningGameService
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)

# --- Навигация по меню игры ---

@router.callback_query(F.data == "menu_mining")
@router.message(F.text == "💎 Виртуальный Майнинг")
async def game_entry_point(update: Union[CallbackQuery, Message], state: FSMContext, admin_service: AdminService):
    """Точка входа в игру."""
    await admin_service.track_command_usage("💎 Виртуальный Майнинг")
    await state.set_state(MiningGameStates.main_menu)
    message, _ = await get_message_and_chat_id(update)
    await message.answer("<b>💎 Центр управления Виртуальным Майнингом</b>", reply_markup=get_mining_menu_keyboard().as_markup())
    if isinstance(update, CallbackQuery):
        await update.answer()

@router.callback_query(F.data.startswith("game_nav:"))
async def handle_game_navigation(call: CallbackQuery, state: FSMContext, game_service: MiningGameService):
    """Единый обработчик навигации по игре."""
    await call.answer()
    nav_path = call.data.split(":")[1:]
    action = nav_path[0]
    
    if action == "main_menu":
        await state.set_state(MiningGameStates.main_menu)
        await call.message.edit_text("<b>💎 Центр управления Виртуальным Майнингом</b>", reply_markup=get_mining_menu_keyboard().as_markup())
    
    elif action == "shop":
        page = int(nav_path[1]) if len(nav_path) > 1 else 0
        await state.set_state(MiningGameStates.shop)
        text, keyboard = await game_service.get_shop_page(page)
        await call.message.edit_text(text, reply_markup=keyboard.as_markup())
        
    elif action == "farm":
        await state.set_state(MiningGameStates.my_farm)
        text = await game_service.get_farm_status_text(call.from_user.id)
        await call.message.edit_text(text, reply_markup=get_my_farm_keyboard().as_markup())
        
    elif action == "stats":
        text = await game_service.get_user_stats_text(call.from_user.id)
        await call.message.edit_text(text, reply_markup=get_my_farm_keyboard().as_markup()) # Используем ту же клавиатуру
        
    elif action == "electricity":
        await state.set_state(MiningGameStates.electricity_menu)
        text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
        await call.message.edit_text(text, reply_markup=keyboard.as_markup())
        
    elif action == "invite":
        text = await game_service.get_invite_text(call.from_user.id)
        # Отправляем новым сообщением, чтобы ссылку было удобно копировать
        await call.message.answer(text)
        
    elif action == "withdraw":
        success, text = await game_service.process_withdrawal(call.from_user.id)
        if success:
            await call.message.edit_text(text, reply_markup=get_withdraw_keyboard().as_markup())
        else:
            await call.answer(text, show_alert=True)

# --- Обработка действий в игре ---

@router.callback_query(F.data.startswith("game_action:"))
async def handle_game_actions(call: CallbackQuery, state: FSMContext, game_service: MiningGameService):
    """Единый обработчик для игровых действий."""
    action_path = call.data.split(":")[1:]
    action = action_path[0]
    user_id = call.from_user.id

    if action == "start_mining":
        asic_index = int(action_path[1])
        success, text = await game_service.start_mining_session(user_id, asic_index)
        if success:
            await call.message.edit_text(text, reply_markup=get_mining_menu_keyboard().as_markup())
        else:
            await call.answer(text, show_alert=True)
            
    elif action == "select_tariff":
        tariff_name = action_path[1]
        success, text = await game_service.select_tariff(user_id, tariff_name)
        await call.answer(text, show_alert=not success)
        if success:
             # Обновляем меню
            text, keyboard = await game_service.get_electricity_menu(user_id)
            await call.message.edit_text(text, reply_markup=keyboard.as_markup())
            
    elif action == "buy_tariff":
        tariff_name = action_path[1]
        success, text = await game_service.buy_tariff(user_id, tariff_name)
        await call.answer(text, show_alert=True)
        if success:
            # Обновляем меню
            text, keyboard = await game_service.get_electricity_menu(user_id)
            await call.message.edit_text(text, reply_markup=keyboard.as_markup())

# --- Команда /tip ---
@router.message(Command("tip"))
async def handle_tip_command(message: Message, game_service: MiningGameService):
    """Обрабатывает отправку чаевых."""
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать ответом на сообщение.")
        return
        
    success, text = await game_service.process_tip(
        sender=message.from_user,
        recipient=message.reply_to_message.from_user,
        args=message.text.split()
    )
    await message.reply(text, disable_web_page_preview=True)
