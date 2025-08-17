# ======================================================================================
# File: bot/handlers/public/menu_handlers.py (ПРОДАКШН-ВЕРСИЯ 2025 - РЕФАКТОРИНГ)
# Описание: Обрабатывает возврат в главное меню.
# Исправления:
#   • Всегда вызывается callback.answer(), чтобы не висела «загрузка»
#   • Никаких циклических импортов; show_main_menu_from_callback — единственная зависимость
# ======================================================================================

from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.callback_factories import MenuCallback
from bot.utils.ui_helpers import show_main_menu_from_callback

router = Router(name="main_menu_router")
logger = logging.getLogger(__name__)


@router.callback_query(MenuCallback.filter(F.action == "main"))
async def main_menu_returner(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает все нажатия на кнопки «Назад в главное меню»
    и возвращает пользователя в исходное состояние.
    """
    await call.answer()
    await state.clear()
    await show_main_menu_from_callback(call)