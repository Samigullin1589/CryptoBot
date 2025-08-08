# =================================================================================
# Файл: bot/handlers/public/crypto_center_handler.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Полнофункциональный обработчик для раздела "Крипто-Центр".
# =================================================================================

import logging
from math import ceil
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from bot.utils.dependencies import Deps
from bot.states.info_states import CryptoCenterStates
from bot.keyboards.crypto_center_keyboards import (
    get_crypto_center_main_menu_keyboard,
    get_airdrop_list_keyboard,
    get_airdrop_details_keyboard,
    get_mining_alpha_keyboard,
    get_news_feed_keyboard,
    CC_CALLBACK_PREFIX
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)
PAGE_SIZE = 5

@router.callback_query(F.data == "nav:crypto_center")
@router.callback_query(F.data == f"{CC_CALLBACK_PREFIX}:main")
async def crypto_center_main_menu(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(CryptoCenterStates.main_menu)
    text = ("💎 <b>Крипто-Центр</b>\n\n"
            "Ваш персональный AI-ассистент в мире криптовалют. "
            "Анализирует новости и ваш профиль интересов, чтобы находить лучшие возможности.")
    keyboard = get_crypto_center_main_menu_keyboard()
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:airdrops:list:"))
async def airdrop_list_handler(call: types.CallbackQuery, deps: Deps, state: FSMContext):
    await state.set_state(CryptoCenterStates.airdrop_list)
    page = int(call.data.split(":")[-1])
    projects = await deps.crypto_center_service.get_airdrop_alpha(call.from_user.id)
    
    if not projects:
        text = "💎 <b>Airdrop Alpha</b>\n\nНа основе анализа новостей и вашего профиля, AI пока не нашел подходящих проектов. Загляните позже!"
        await call.message.edit_text(text, reply_markup=get_crypto_center_main_menu_keyboard())
        await call.answer()
        return

    total_pages = ceil(len(projects) / PAGE_SIZE)
    start_index, end_index = page * PAGE_SIZE, (page + 1) * PAGE_SIZE
    
    text = "💎 <b>Airdrop Alpha (Персональная подборка)</b>\n\nНажмите на проект, чтобы увидеть детали и чек-лист задач."
    keyboard = get_airdrop_list_keyboard(projects[start_index:end_index], page, total_pages)
    
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:airdrops:view:"))
async def airdrop_view_handler(call: types.CallbackQuery, deps: Deps, state: FSMContext):
    await state.set_state(CryptoCenterStates.airdrop_view)
    project_id = call.data.split(":")[-1]
    projects = await deps.crypto_center_service.get_airdrop_alpha(call.from_user.id)
    project = next((p for p in projects if p.id == project_id), None)

    if not project:
        await call.answer("❌ Проект не найден. Возможно, он устарел.", show_alert=True)
        return

    completed_tasks = await deps.crypto_center_service.get_user_progress(call.from_user.id, project_id)
    
    text = (f"<b>{project.name}</b>\n\n"
            f"<i>{project.description}</i>\n\n"
            f"<b>Статус:</b> {project.status}\n\n"
            "<b>Чек-лист для выполнения:</b>")
    keyboard = get_airdrop_details_keyboard(project, completed_tasks)

    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:airdrops:task:"))
async def airdrop_task_toggle_handler(call: types.CallbackQuery, deps: Deps, state: FSMContext):
    parts = call.data.split(":")
    project_id, task_index = parts[-2], int(parts[-1])
    await deps.crypto_center_service.toggle_task_status(call.from_user.id, project_id, task_index)
    # Обновляем текущее сообщение, чтобы показать изменение статуса задачи
    await airdrop_view_handler(call, deps, state)

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:mining:list:"))
async def mining_list_handler(call: types.CallbackQuery, deps: Deps):
    await call.answer("Этот раздел в разработке.", show_alert=True)

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:news:list:"))
async def news_list_handler(call: types.CallbackQuery, deps: Deps):
    await call.answer("Этот раздел в разработке.", show_alert=True)
