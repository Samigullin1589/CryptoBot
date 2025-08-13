# =================================================================================
# Файл: bot/handlers/public/market_info_handler.py (ВЕРСИЯ "Distinguished Engineer" - РЕФАКТОРИНГ)
# Описание: Обрабатывает запросы на получение общих рыночных данных.
# ИСПРАВЛЕНИЕ: Добавлены фильтры MenuCallback для прямого отклика на кнопки меню.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.keyboards.callback_factories import MenuCallback
from bot.utils.formatters import format_halving_info, format_network_status
from bot.utils.plotting import generate_fng_image

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(MenuCallback.filter(F.action == "fear_index"))
async def handle_fear_greed_index(call: CallbackQuery, deps: Deps, state: FSMContext):
    await call.answer()
    temp_message = await call.message.edit_text("⏳ Загружаю индекс и генерирую пояснение от AI...")
    
    try:
        data = await deps.market_data_service.get_fear_and_greed_index()
        if not data: raise ValueError("API индекса страха и жадности не вернул данных.")

        value = int(data['value'])
        classification = data['value_classification']
        
        image_bytes = generate_fng_image(value, classification)
        photo = BufferedInputFile(image_bytes, filename="fng_index.png")
        
        ai_question = (f"Кратко, в 1-2 предложениях, объясни простым языком, что означает 'Индекс страха и жадности' {value} ({classification}).")
        ai_explanation = await deps.ai_content_service.get_consultant_answer(ai_question, history=[])

        base_caption = f"😱 <b>Индекс страха и жадности:</b> {value}\n<i>Состояние рынка: {classification}</i>"
        final_caption = base_caption
        if ai_explanation and "недоступен" not in ai_explanation:
            final_caption += f"\n\n<b>Пояснение от AI:</b>\n{ai_explanation}"

        await temp_message.delete()
        await call.message.answer_photo(photo=photo, caption=final_caption, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения индекса страха и жадности: {e}", exc_info=True)
        await temp_message.edit_text("😕 Не удалось загрузить данные индекса.")

@router.callback_query(MenuCallback.filter(F.action == "halving"))
async def handle_halving_info(call: CallbackQuery, deps: Deps, state: FSMContext):
    await call.answer("Загружаю данные о халвинге...")
    try:
        data = await deps.market_data_service.get_halving_info()
        if not data: raise ValueError("API для халвинга не вернул валидных данных.")
        
        text = format_halving_info(data)
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения данных о халвинге: {e}", exc_info=True)
        await call.answer("Не удалось загрузить данные.", show_alert=True)

@router.callback_query(MenuCallback.filter(F.action == "btc_status"))
async def handle_btc_status(call: CallbackQuery, deps: Deps, state: FSMContext):
    await call.answer()
    temp_message = await call.message.edit_text("⏳ Загружаю статус сети и запрашиваю анализ у AI...")
    try:
        data = await deps.market_data_service.get_btc_network_status()
        if not data: raise ValueError("Сервис не вернул данные о статусе сети BTC.")

        text = format_network_status(data)
        hashrate_ehs = data.get('hashrate_ehs', 0.0)
        ai_question = (f"Хешрейт сети Bitcoin сейчас ~{hashrate_ehs:.0f} EH/s. Кратко, в 1-2 предложениях, объясни простым языком, что это значит.")
        ai_explanation = await deps.ai_content_service.get_consultant_answer(ai_question, history=[])
        
        if ai_explanation and "недоступен" not in ai_explanation:
            text += f"\n\n<b>Что это значит (анализ AI):</b>\n{ai_explanation}"

        await temp_message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения статуса сети BTC: {e}", exc_info=True)
        await temp_message.edit_text("😕 Не удалось загрузить данные о статусе сети.")