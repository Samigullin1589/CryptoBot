# ======================================================================================
# File: bot/handlers/public/menu_handlers.py
# Version: "Distinguished Engineer" — ИСПРАВЛЕНО (28.10.2025)
# Описание: Обрабатывает возврат в главное меню.
# ИСПРАВЛЕНО: Добавлен импорт ParseMode (на случай если понадобится)
# ВАЖНО: Проверьте что в bot/utils/ui_helpers.py в функции show_main_menu_from_callback
#        тоже используется parse_mode=ParseMode.HTML!
# ======================================================================================

from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode  # ← ДОБАВЛЕНО (для будущего использования)

from bot.keyboards.callback_factories import MenuCallback
from bot.utils.ui_helpers import show_main_menu_from_callback

router = Router(name="main_menu_router")
logger = logging.getLogger(__name__)


@router.callback_query(MenuCallback.filter(F.action == "main"))
async def main_menu_returner(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает все нажатия на кнопки «Назад в главное меню»
    и возвращает пользователя в исходное состояние.
    
    ВАЖНО: Убедитесь что функция show_main_menu_from_callback()
    в bot/utils/ui_helpers.py использует parse_mode=ParseMode.HTML
    """
    await call.answer()
    await state.clear()
    await show_main_menu_from_callback(call)