# =================================================================================
# Файл: bot/handlers/public/menu_handlers.py (ПРОДАКШН-ВЕРСИЯ 2025, С ФАБРИКАМИ)
# Описание: Центральный роутер, использующий CallbackData для навигации.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.callback_factories import MenuCallback
from bot.utils.dependencies import Deps
from bot.utils.ui_helpers import show_main_menu_from_callback

# Импортируем целевые обработчики
from . import price_handler # и другие по мере реализации

router = Router(name="main_menu_router")
logger = logging.getLogger(__name__)

# --- ЦЕНТРАЛЬНЫЙ ОБРАБОТЧИК НАВИГАЦИИ ---
# Фильтруем по объекту MenuCallback, где level=0 (главное меню)
@router.callback_query(MenuCallback.filter(F.level == 0))
async def main_menu_navigator(call: CallbackQuery, callback_data: MenuCallback, state: FSMContext, deps: Deps):
    """
    Принимает нажатия на кнопки главного меню и перенаправляет в нужные модули.
    """
    await state.clear()
    action = callback_data.action
    
    if action == "main":
        await show_main_menu_from_callback(call, deps)
        return

    navigation_map = {
        "price": price_handler.handle_price_menu_start,
        # "asics": asic_handler.handle_asic_menu_start, # Будет добавлено
    }
    
    handler_func = navigation_map.get(action)
    
    if handler_func:
        await handler_func(call, state, deps)
    else:
        logger.warning(f"Не найден обработчик для действия 'menu:0:{action}'")
        await call.answer(f"Раздел '{action}' в разработке.", show_alert=True)
