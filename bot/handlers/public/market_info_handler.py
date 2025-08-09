# =================================================================================
# Файл: bot/handlers/public/market_info_handler.py (ВЕРСИЯ "Distinguished Engineer" - ИСПРАВЛЕННАЯ)
# Описание: Обрабатывает запросы на получение общих рыночных данных.
# ИСПРАВЛЕНИЕ: Убраны лишние аргументы из сигнатур функций для устранения TypeError.
# =================================================================================
import logging
from datetime import datetime
from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.utils.http_client import make_request

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "nav:fear_index")
async def handle_fear_greed_index(call: CallbackQuery, deps: Deps, **kwargs):
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

@router.callback_query(F.data == "nav:halving")
async def handle_halving_info(call: CallbackQuery, deps: Deps, **kwargs):
    """Получает и отображает информацию о халвинге Bitcoin."""
    await call.answer("Загружаю данные о халвинге...")
    try:
        data = await make_request(deps.http_session, str(deps.settings.endpoints.mempool_space_difficulty))
        progress = data.get('progressPercent', 0)
        remaining_blocks = data.get('remainingBlocks', 0)
        estimated_date = datetime.fromtimestamp(data.get('nextRetargetTimeEstimate')).strftime('%d.%m.%Y')
        text = (f"⏳ <b>Халвинг Bitcoin</b>\n\n"
                f"Прогресс до следующего халвинга: <b>{progress:.2f}%</b>\n"
                f"Осталось блоков: <b>{remaining_blocks:,}</b>\n"
                f"Ориентировочная дата: <b>{estimated_date}</b>")
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения данных о халвинге: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)

@router.callback_query(F.data == "nav:btc_status")
async def handle_btc_status(call: CallbackQuery, deps: Deps, **kwargs):
    """Получает и отображает текущий статус сети Bitcoin."""
    await call.answer("Загружаю статус сети...")
    try:
        hashrate_ths = await make_request(deps.http_session, str(deps.settings.endpoints.blockchain_info_hashrate), response_type="text")
        hashrate_ehs = float(hashrate_ths) / 1_000_000 # TH/s -> EH/s
        text = f"📡 <b>Статус сети Bitcoin</b>\n\nХешрейт: <b>{hashrate_ehs:.2f} EH/s</b>"
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения статуса сети BTC: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)