# =================================================================================
# Файл: bot/handlers/public/market_info_handler.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Обрабатывает запросы на получение общих рыночных данных.
# =================================================================================
import logging
from datetime import datetime
from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "nav:market_fear_greed")
async def handle_fear_greed_index(call: CallbackQuery, deps: Deps):
    """Получает и отображает индекс страха и жадности."""
    await call.answer("Загружаю индекс...")
    try:
        async with deps.http_session.get(str(deps.settings.endpoints.fear_and_greed_api)) as response:
            response.raise_for_status()
            data = await response.json()
            value = int(data['data'][0]['value'])
            classification = data['data'][0]['value_classification']
            emoji = {"Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", "Greed": "😏", "Extreme Greed": "🤑"}.get(classification, "")
            text = f"😱 <b>Индекс страха и жадности:</b> {value} {emoji}\n\n<i>Состояние рынка: {classification}</i>"
            await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения индекса страха и жадности: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)

@router.callback_query(F.data == "nav:market_halving")
async def handle_halving_info(call: CallbackQuery, deps: Deps):
    """Получает и отображает информацию о халвинге Bitcoin."""
    await call.answer("Загружаю данные о халвинге...")
    try:
        async with deps.http_session.get(str(deps.settings.endpoints.mempool_space_difficulty)) as response:
            response.raise_for_status()
            data = await response.json()
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

@router.callback_query(F.data == "nav:market_btc_status")
async def handle_btc_status(call: CallbackQuery, deps: Deps):
    """Получает и отображает текущий статус сети Bitcoin."""
    await call.answer("Загружаю статус сети...")
    try:
        async with deps.http_session.get(str(deps.settings.endpoints.blockchain_info_hashrate)) as response:
            response.raise_for_status()
            hashrate_ths = float(await response.text()) / 1_000_000 # TH/s -> EH/s
            text = f"📡 <b>Статус сети Bitcoin</b>\n\nХешрейт: <b>{hashrate_ths:.2f} EH/s</b>"
            await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения статуса сети BTC: {e}")
        await call.answer("Не удалось загрузить данные.", show_alert=True)
