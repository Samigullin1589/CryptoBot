# =================================================================================
# Файл: bot/handlers/public/market_data_handler.py (ВЕРСЯ "Distinguished Engineer" - ИСПРАВЛЕННАЯ)
# Описание: Обрабатывает запросы на получение общих рыночных данных.
# ИСПРАВЛЕНИЕ: Убраны лишние аргументы из сигнатур функций для устранения TypeError.
#               Переход на фабрику MenuCallback.
# =================================================================================
import logging
from datetime import datetime
from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.keyboards.callback_factories import MenuCallback
from bot.utils.http_client import make_request

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(MenuCallback.filter(F.action == "fear_index"))
async def handle_fear_greed_index(call: CallbackQuery, deps: Deps):
    """Получает и отображает индекс страха и жадности."""
    await call.answer("Загружаю индекс...")
    try:
        data = await make_request(deps.http_session, str(deps.settings.endpoints.fear_and_greed_api))
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        emoji = {"Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", "Greed": "😏", "Extreme Greed": "🤑"}.get(classification, "")
        text = f"😱 <b>Индекс страха и жадности:</b> {value} {emoji}\n\n<i>Состояние рынка: {classification}</i>"
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения индекса страха и жадности: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)

@router.callback_query(MenuCallback.filter(F.action == "halving"))
async def handle_halving_info(call: CallbackQuery, deps: Deps):
    """Получает и отображает информацию о халвинге Bitcoin."""
    await call.answer("Загружаю данные о халвинге...")
    try:
        data = await deps.market_data_service.get_halving_info()
        if not data:
             raise ValueError("Не удалось получить данные о халвинге")
        progress = data.get('progressPercent', 0)
        remaining_blocks = data.get('remainingBlocks', 0)
        estimated_date = data.get('estimated_date', 'неизвестно')
        text = (f"⏳ <b>Халвинг Bitcoin</b>\n\n"
                f"Прогресс до следующего халвинга: <b>{progress:.2f}%</b>\n"
                f"Осталось блоков: <b>{remaining_blocks:,}</b>\n"
                f"Ориентировочная дата халвинга: <b>{estimated_date}</b>")
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения данных о халвинге: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)

@router.callback_query(MenuCallback.filter(F.action == "btc_status"))
async def handle_btc_status(call: CallbackQuery, deps: Deps):
    """Получает и отображает текущий статус сети Bitcoin."""
    await call.answer("Загружаю статус сети...")
    try:
        network_status = await deps.market_data_service.get_btc_network_status()
        if not network_status:
            raise ValueError("Не удалось получить статус сети")

        hashrate_ehs = network_status.get('hashrate_ehs', 0.0)
        difficulty_change = network_status.get('difficulty_change', 0.0)
        estimated_retarget_date = network_status.get('estimated_retarget_date', 'N/A')
        
        change_sign = "+" if difficulty_change > 0 else ""

        text = (f"📡 <b>Статус сети Bitcoin</b>\n\n"
                f"Хешрейт: <b>{hashrate_ehs:.2f} EH/s</b>\n"
                f"След. изменение сложности: <b>~{change_sign}{difficulty_change:.2f}%</b>\n"
                f"<i>(Ориентировочно {estimated_retarget_date})</i>")
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения статуса сети BTC: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)