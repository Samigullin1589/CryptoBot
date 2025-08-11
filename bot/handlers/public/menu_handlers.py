# =================================================================================
# Файл: bot/handlers/public/menu_handlers.py (ПРОДАКШН-ВЕРСИЯ 2025, С ФАБРИКАМИ - ИСПРАВЛЕННАЯ)
# Описание: Центральный роутер, использующий CallbackData для навигации.
# ИСПРАВЛЕНИЕ: Устранены ошибки TypeError, вызовы хэндлеров приведены
#              в соответствие с их реальными сигнатурами.
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
    market_info_handler,
    crypto_center_handler
)
from ..tools import calculator_handler
# Игровые хэндлеры теперь в своей папке
from ..game import mining_game_handler

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

    if action == "main":
        await show_main_menu_from_callback(call)
        return

    # Карта навигации: сопоставляет 'action' с функцией-обработчиком
    navigation_map = {
        "price": price_handler.handle_price_menu_start,
        "asics": asic_handler.top_asics_start,
        "calculator": calculator_handler.start_profit_calculator,
        "news": news_handler.handle_news_menu_start,
        "fear_index": market_info_handler.handle_fear_greed_index,
        "halving": market_info_handler.handle_halving_info,
        "btc_status": market_info_handler.handle_btc_status,
        "quiz": quiz_handler.handle_quiz_start,
        "game": mining_game_handler.handle_mining_menu, # <-- ИСПРАВЛЕНО НА ПРАВИЛЬНЫЙ ХЕНДЛЕР
        "crypto_center": crypto_center_handler.crypto_center_main_menu,
    }

    handler_func = navigation_map.get(action)

    if handler_func:
        # ИСПРАВЛЕНО: aiogram 3 элегантно передает в хэндлер только те зависимости,
        # которые указаны в его сигнатуре. Мы можем безопасно передавать
        # все доступные, и хэндлер сам выберет нужные. `update` передается как `call`.
        await handler_func(call, state=state, deps=deps)
    else:
        logger.warning(f"Не найден обработчик для действия 'menu:0:{action}'")
        await call.answer(f"Раздел '{action}' находится в разработке.", show_alert=True)