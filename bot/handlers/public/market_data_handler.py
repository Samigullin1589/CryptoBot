# ===============================================================
# Файл: bot/handlers/public/market_data_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Обрабатывает запросы на получение рыночных данных,
# таких как Индекс страха и жадности, статус сети Bitcoin и
# информация о халвинге.
# ===============================================================
import logging
import asyncio
from typing import Union

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.keyboards.info_keyboards import get_main_menu_keyboard
from bot.services.market_data_service import MarketDataService
from bot.utils.plotting import generate_fng_image
from bot.utils.formatters import format_halving_info, format_network_status
# --- ИСПРАВЛЕНИЕ: Импортируем из правильного модуля ---
from bot.utils.ui_helpers import show_main_menu_from_callback
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


# Инициализация роутера
router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- ОБРАБОТЧИКИ ДЛЯ РАЗНЫХ ТИПОВ РЫНОЧНЫХ ДАННЫХ ---

@router.callback_query(F.data == "nav:fear_greed")
async def handle_fear_greed_menu(call: CallbackQuery, market_data_service: MarketDataService):
    """
    Обрабатывает запрос на получение Индекса страха и жадности.
    Генерирует и отправляет изображение.
    """
    await call.message.delete()
    temp_message = await call.message.answer("⏳ Получаю индекс и рисую график...")

    index = await market_data_service.get_fear_and_greed_index()
    if not index:
        await temp_message.edit_text("❌ Не удалось получить Индекс страха и жадности.", reply_markup=get_main_menu_keyboard())
        return

    # Генерируем изображение в фоновом потоке, чтобы не блокировать бота
    loop = asyncio.get_running_loop()
    image_bytes = await loop.run_in_executor(
        None, generate_fng_image, index.value, index.value_classification
    )
    
    caption = f"😱 <b>Индекс страха и жадности: {index.value} - {index.value_classification}</b>"

    await temp_message.delete()
    await call.message.answer_photo(
        BufferedInputFile(image_bytes, "fng.png"), 
        caption=caption, 
        reply_markup=get_main_menu_keyboard()
    )

@router.callback_query(F.data.startswith("nav:"))
async def handle_market_data_navigation(call: CallbackQuery, market_data_service: MarketDataService):
    """
    Универсальный обработчик для кнопок "Халвинг" и "Статус BTC".
    """
    action = call.data.split(':')[1]
    
    text = "⏳ Загружаю данные..."
    await call.message.edit_text(text)
    
    response_text = "❌ Произошла ошибка при загрузке данных."

    if action == "halving":
        halving_info = await market_data_service.get_halving_info()
        if halving_info:
            response_text = format_halving_info(halving_info)
    
    elif action == "btc_status":
        network_status = await market_data_service.get_btc_network_status()
        if network_status:
            response_text = format_network_status(network_status)

    await call.message.edit_text(response_text, reply_markup=get_main_menu_keyboard())
