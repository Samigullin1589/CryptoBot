# =================================================================================
# Файл: bot/handlers/public/market_info_handler.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Обрабатывает запросы на получение общих рыночных данных,
#           корректно используя MarketDataService и современные форматтеры.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.utils.dependencies import Deps
from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.utils.formatters import format_halving_info, format_network_status
from bot.utils.plotting import generate_fng_image
from aiogram.types import BufferedInputFile

router = Router(name=__name__)
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "nav:fear_index")
async def handle_fear_greed_index(call: CallbackQuery, deps: Deps):
    """
    Получает, генерирует и отображает изображение индекса страха и жадности.
    """
    await call.answer("Загружаю и генерирую индекс...")
    try:
        data = await deps.market_data_service.get_fear_and_greed_index()
        if not data:
            raise ValueError("API индекса страха и жадности не вернул данных.")

        value = int(data['value'])
        classification = data['value_classification']
        
        # Генерируем изображение
        image_bytes = generate_fng_image(value, classification)
        photo = BufferedInputFile(image_bytes, filename="fng_index.png")
        
        # Удаляем старое текстовое сообщение и отправляем новое с картинкой
        await call.message.delete()
        await call.message.answer_photo(
            photo=photo,
            caption=f"😱 <b>Индекс страха и жадности:</b> {value}\n<i>Состояние рынка: {classification}</i>",
            reply_markup=get_back_to_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка получения индекса страха и жадности: {e}", exc_info=True)
        await call.answer("Не удалось загрузить данные индекса. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "nav:halving")
async def handle_halving_info(call: CallbackQuery, deps: Deps):
    """
    Получает и отображает информацию о халвинге Bitcoin, используя MarketDataService.
    """
    await call.answer("Загружаю данные о халвинге...")
    try:
        data = await deps.market_data_service.get_halving_info()
        if not data:
            raise ValueError("API для халвинга не вернул валидных данных.")
        
        # Используем специализированный форматтер для чистоты кода
        text = format_halving_info(data)
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка получения данных о халвинге: {e}", exc_info=True)
        await call.answer("Не удалось загрузить данные о халвинге.", show_alert=True)

@router.callback_query(F.data == "nav:btc_status")
async def handle_btc_status(call: CallbackQuery, deps: Deps):
    """
    Получает и отображает текущий статус сети Bitcoin, используя MarketDataService.
    """
    await call.answer("Загружаю статус сети...")
    try:
        data = await deps.market_data_service.get_btc_network_status()
        if not data:
            raise ValueError("Сервис не вернул данные о статусе сети BTC.")

        # Используем специализированный форматтер
        text = format_network_status(data)
        await call.message.edit_text(text, reply_markup=get_back_to_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка получения статуса сети BTC: {e}", exc_info=True)
        await call.answer("Не удалось загрузить данные о статусе сети.", show_alert=True)