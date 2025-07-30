# =================================================================================
# Файл: bot/handlers/admin/game_admin_handler.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ПОЛНАЯ И ОКОНЧАТЕЛЬНАЯ)
# Описание: Обработчики для администрирования игровой части бота.
# =================================================================================

import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from bot.filters.access_filters import PrivilegeFilter
from bot.services.admin_service import AdminService
from bot.keyboards.admin_keyboards import get_game_admin_menu_keyboard, get_back_to_game_admin_menu_keyboard, GAME_ADMIN_CALLBACK_PREFIX
from bot.states.admin_states import GameAdminStates

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(PrivilegeFilter("ADMIN"))
router.callback_query.filter(PrivilegeFilter("ADMIN"))

@router.callback_query(F.data == f"{GAME_ADMIN_CALLBACK_PREFIX}:menu")
async def game_admin_menu_handler(callback: types.CallbackQuery, admin_service: AdminService, state: FSMContext):
    """Отображает главное меню управления игрой."""
    await state.clear()
    stats = await admin_service.get_game_stats()
    text = "🎮 <b>Панель Управления Игрой</b>"
    keyboard = get_game_admin_menu_keyboard(stats)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == f"{GAME_ADMIN_CALLBACK_PREFIX}:balance_start")
async def change_balance_start_handler(callback: types.CallbackQuery, state: FSMContext):
    """Начинает сценарий изменения баланса."""
    await state.set_state(GameAdminStates.entering_user_id_for_balance)
    text = "Введите User ID пользователя, которому вы хотите изменить баланс."
    keyboard = get_back_to_game_admin_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.message(StateFilter(GameAdminStates.entering_user_id_for_balance))
async def change_balance_enter_id_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ввод User ID."""
    try:
        user_id = int(message.text)
    except (ValueError, TypeError):
        await message.answer("❌ ID должен быть числом. Попробуйте снова.")
        return
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(GameAdminStates.entering_balance_amount)
    await message.answer("Теперь введите сумму для изменения баланса. \n"
                         "Используйте положительное число для начисления (e.g., `1000`) "
                         "и отрицательное для списания (e.g., `-500`).")

@router.message(StateFilter(GameAdminStates.entering_balance_amount))
async def change_balance_enter_amount_handler(message: types.Message, state: FSMContext, admin_service: AdminService):
    """Обрабатывает ввод суммы и завершает операцию."""
    try:
        amount = float(message.text)
    except (ValueError, TypeError):
        await message.answer("❌ Сумма должна быть числом. Попробуйте снова.")
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    new_balance = await admin_service.change_user_game_balance(target_user_id, amount)
    await state.clear()
    
    if new_balance is not None:
        await message.answer(f"✅ Баланс пользователя <code>{target_user_id}</code> успешно изменен. \n"
                             f"Новый баланс: <b>{new_balance:,.2f} монет</b>.", 
                             reply_markup=get_back_to_game_admin_menu_keyboard())
        try:
            change_text = f"начислены {amount:,.2f}" if amount > 0 else f"списаны {-amount:,.2f}"
            await message.bot.send_message(
                chat_id=target_user_id,
                text=f"⚠️ Администратор изменил ваш игровой баланс. Вам были {change_text} монет."
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить пользователя {target_user_id} об изменении баланса: {e}")
    else:
        await message.answer(f"❌ Не удалось найти игровой профиль для пользователя с ID <code>{target_user_id}</code>.",
                             reply_markup=get_back_to_game_admin_menu_keyboard())