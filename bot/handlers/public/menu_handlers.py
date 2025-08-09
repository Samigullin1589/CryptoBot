# =================================================================================
# Файл: bot/handlers/public/menu_handlers.py (ПРОДАКШН-ВЕРСИЯ 2025, С ФАБРИКАМИ - ИСПРАВЛЕННАЯ)
# Описание: Центральный роутер, использующий CallbackData для навигации.
# ИСПРАВЛЕНИЕ: Устранена ошибка TypeError и реализована полная карта
# навигации для всех кнопок главного меню.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.callback_factories import MenuCallback
from bot.utils.dependencies import Deps
from bot.utils.ui_helpers import show_main_menu_from_callback

# Импортируем все необходимые хэндлеры для навигации
from . import (
    price_handler,
    asic_handler,
    news_handler,
    quiz_handler,
    game_handler,
    market_data_handler,
    crypto_center_handler
)
from ..tools import calculator_handler

router = Router(name="main_menu_router")
logger = logging.getLogger(__name__)

# --- ЦЕНТРАЛЬНЫЙ ОБРАБОТЧИК НАВИГАЦИИ ---
@router.callback_query(MenuCallback.filter(F.level == 0))
async def main_menu_navigator(call: CallbackQuery, callback_data: MenuCallback, state: FSMContext, deps: Deps):
    """
    Принимает нажатия на кнопки главного меню и перенаправляет в нужные модули.
    """
    await state.clear()
    action = callback_data.action

    # Действие для возврата в главное меню
    if action == "main":
        # ИСПРАВЛЕНО: Убран лишний аргумент `deps`, вызывавший TypeError
        await show_main_menu_from_callback(call)
        return

    # Карта навигации: сопоставляет 'action' из callback'а с функцией-обработчиком
    navigation_map = {
        "price": price_handler.handle_price_menu_start,
        "asics": asic_handler.top_asics_start,
        "calculator": calculator_handler.start_profit_calculator,
        "news": news_handler.handle_news_menu_start,
        "fear_index": market_data_handler.handle_fear_greed_menu,
        "halving": market_data_handler.handle_market_data_navigation,
        "btc_status": market_data_handler.handle_market_data_navigation,
        "quiz": quiz_handler.handle_quiz_start,
        "game": game_handler.handle_game_menu_entry,
        "crypto_center": crypto_center_handler.crypto_center_main_menu,
    }

    handler_func = navigation_map.get(action)

    if handler_func:
        # Для хэндлеров, которые исторически зависели от `call.data`, 
        # мы его временно подменяем для обратной совместимости.
        if action in ["halving", "btc_status"]:
            call.data = f"nav:{action}"

        # Aiogram 3 элегантно передает в хэндлер только те зависимости,
        # которые указаны в его сигнатуре. Просто передаем все доступные.
        await handler_func(call, state=state, deps=deps)
    else:
        logger.warning(f"Не найден обработчик для действия 'menu:0:{action}'")
        await call.answer(f"Раздел '{action}' находится в разработке.", show_alert=True)