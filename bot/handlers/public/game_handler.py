# =================================================================================
# Файл: bot/handlers/public/game_handler.py (ВЕРСЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Полнофункциональный обработчик для раздела "Виртуальный Майнинг".
# Управляет FSM, навигацией и запуском игровых сессий.
# ИСПРАВЛЕНИЕ: Переход на использование GameCallback и MenuCallback.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.utils.dependencies import Deps
from bot.states.game_states import MiningGameStates
from bot.keyboards.callback_factories import MenuCallback, GameCallback
from bot.keyboards.game_keyboards import get_game_main_menu_keyboard, get_hangar_keyboard

router = Router(name=__name__)
logger = logging.getLogger(__name__)

async def show_game_menu(call: CallbackQuery, deps: Deps, state: FSMContext):
    """Отображает главное меню игры, обновляя информацию."""
    await state.set_state(MiningGameStates.main_menu)
    farm_info, stats_info = await deps.mining_game_service.get_farm_and_stats_info(call.from_user.id)
    session_data = await deps.redis_pool.hgetall(deps.keys.active_session(call.from_user.id))
    is_session_active = bool(session_data)

    text = f"{farm_info}\n\n{stats_info}"
    keyboard = get_game_main_menu_keyboard(is_session_active)

    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()

@router.callback_query(MenuCallback.filter(F.action == "game"))
async def handle_game_menu_entry_from_main(call: CallbackQuery, deps: Deps, state: FSMContext):
    """Точка входа в игровой раздел из главного меню."""
    await show_game_menu(call, deps, state)

@router.callback_query(GameCallback.filter(F.action == "main_menu"))
async def handle_game_menu_entry_from_game(call: CallbackQuery, deps: Deps, state: FSMContext):
    """Точка входа в игровой раздел (внутренняя навигация)."""
    await show_game_menu(call, deps, state)

@router.callback_query(GameCallback.filter(F.action == "start_session"), MiningGameStates.main_menu)
async def handle_start_session_prompt(call: CallbackQuery, deps: Deps, state: FSMContext):
    """Отображает ангар для выбора ASIC для запуска."""
    await state.set_state(MiningGameStates.choosing_asic_for_session)
    await state.update_data(page=0)

    user_asics = await deps.mining_game_service.get_user_asics(call.from_user.id)

    text = "🛠 <b>Выберите оборудование из ангара для запуска сессии:</b>"
    if not user_asics:
        text = "🛠 <b>Ваш ангар пуст.</b>\n\nПриобретите оборудование на рынке, чтобы начать майнинг."

    keyboard = get_hangar_keyboard(user_asics, page=0)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()

@router.callback_query(GameCallback.filter(F.action == "hangar"), MiningGameStates.choosing_asic_for_session)
async def handle_hangar_pagination(call: CallbackQuery, callback_data: GameCallback, deps: Deps, state: FSMContext):
    """Обрабатывает пагинацию в ангаре."""
    page = callback_data.page
    await state.update_data(page=page)

    user_asics = await deps.mining_game_service.get_user_asics(call.from_user.id)
    keyboard = get_hangar_keyboard(user_asics, page)

    await call.message.edit_reply_markup(reply_markup=keyboard)
    await call.answer()

@router.callback_query(GameCallback.filter(F.action == "session_start_confirm"), MiningGameStates.choosing_asic_for_session)
async def handle_start_session_action(call: CallbackQuery, callback_data: GameCallback, deps: Deps, state: FSMContext):
    """Запускает сессию майнинга для выбранного ASIC."""
    asic_id = callback_data.value

    await call.answer("🚀 Запускаю сессию...")

    result_text = await deps.mining_game_service.start_session(call.from_user.id, asic_id)

    await call.message.answer(result_text, disable_web_page_preview=True)
    await show_game_menu(call, deps, state)