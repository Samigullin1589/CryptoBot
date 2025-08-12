# =================================================================================
# Файл: bot/handlers/public/market_info_handler.py (ВЕРСИЯ "Distinguished Engineer" - с AI-пояснениями)
# Описание: Обрабатывает запросы на получение общих рыночных данных,
#           дополняя их динамическими пояснениями от AI.
# ИСПРАВЛЕНИЕ: Добавлена логика вызова AI для объяснения статуса сети Bitcoin.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.utils.formatters import format_halving_info, format_network_status
from bot.utils.plotting import generate_fng_image

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "nav:fear_index")
async def handle_fear_greed_index(call: CallbackQuery, deps: Deps, state: FSMContext):
    """
    Получает индекс, генерирует изображение и запрашивает у AI
    актуальное пояснение для текущего состояния рынка.
    """
    await call.answer()
    temp_message = await call.message.edit_text("⏳ Загружаю индекс и генерирую пояснение от AI...")
    
    try:
        data = await deps.market_data_service.get_fear_and_greed_index()
        if not data:
            raise ValueError("API индекса страха и жадности не вернул данных.")

        value = int(data['value'])
        classification = data['value_classification']
        
        # 1. Генерируем изображение индекса
        image_bytes = generate_fng_image(value, classification)
        photo = BufferedInputFile(image_bytes, filename="fng_index.png")
        
        # 2. Формируем специальный вопрос для AI
        ai_question = (
            f"Выступи в роли крипто-аналитика. Кратко, в 1-2 предложениях, объясни простым языком, "
            f"что означает текущее значение 'Индекса страха и жадности' равное {value} (классификация: {classification}). "
            f"Опиши настроения на рынке, но не давай прямых финансовых советов."
        )
        
        # 3. Получаем пояснение от AI-консультанта
        ai_explanation = await deps.ai_content_service.get_consultant_answer(ai_question, history=[])

        # 4. Собираем финальное сообщение
        base_caption = f"😱 <b>Индекс страха и жадности:</b> {value}\n<i>Состояние рынка: {classification}</i>"
        final_caption = base_caption
        if ai_explanation and "недоступен" not in ai_explanation:
            final_caption += f"\n\n<b>Пояснение от AI:</b>\n{ai_explanation}"

        # 5. Отправляем результат
        await temp_message.delete()
        await call.message.answer_photo(
            photo=photo,
            caption=final_caption,
            reply_markup=get_back_to_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка получения индекса страха и жадности: {e}", exc_info=True)
        await temp_message.edit_text("😕 Не удалось загрузить данные индекса. Попробуйте позже.")
        await call.answer("Не удалось загрузить данные индекса. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "nav:halving")
async def handle_halving_info(call: CallbackQuery, deps: Deps, state: FSMContext):
    """
    Получает и отображает информацию о халвинге Bitcoin, используя MarketDataService.
    """
    await call.answer("Загружаю данные о халвинге...")
    try:
        data = await deps.market_data_service.get_halving_info()
        if not data:
            raise ValueError("API для халвинга не вернул валидных данных.")
        
        text = format_halving_info(data)
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка получения данных о халвинге: {e}", exc_info=True)
        await call.answer("Не удалось загрузить данные о халвинге.", show_alert=True)


@router.callback_query(F.data == "nav:btc_status")
async def handle_btc_status(call: CallbackQuery, deps: Deps, state: FSMContext):
    """
    Получает и отображает текущий статус сети Bitcoin, дополняя его пояснением от AI.
    """
    await call.answer()
    temp_message = await call.message.edit_text("⏳ Загружаю статус сети и запрашиваю анализ у AI...")
    try:
        data = await deps.market_data_service.get_btc_network_status()
        if not data:
            raise ValueError("Сервис не вернул данные о статусе сети BTC.")

        # 1. Форматируем базовую информацию
        text = format_network_status(data)
        
        # 2. Формируем специальный вопрос для AI
        hashrate_ehs = data.get('hashrate_ehs', 0.0)
        ai_question = (
            f"Выступи в роли крипто-аналитика. Хешрейт сети Bitcoin сейчас составляет примерно {hashrate_ehs:.0f} EH/s. "
            f"Кратко, в 1-2 предложениях, объясни простым языком, что это значит для обычного пользователя или майнера. "
            f"Это высокое или низкое значение? Как это влияет на безопасность сети? Не давай финансовых советов."
        )

        # 3. Получаем пояснение от AI
        ai_explanation = await deps.ai_content_service.get_consultant_answer(ai_question, history=[])
        
        # 4. Собираем финальное сообщение
        if ai_explanation and "недоступен" not in ai_explanation:
            text += f"\n\n<b>Что это значит (анализ AI):</b>\n{ai_explanation}"

        await temp_message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка получения статуса сети BTC: {e}", exc_info=True)
        await temp_message.edit_text("😕 Не удалось загрузить данные о статусе сети.")
        await call.answer("Не удалось загрузить данные о статусе сети.", show_alert=True)