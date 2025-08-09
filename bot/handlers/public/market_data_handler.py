# ===============================================================
# Файл: bot/handlers/public/market_data_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - ИСПРАВЛЕННАЯ)
# Описание: Обрабатывает запросы на получение рыночных данных.
# ИСПРАВЛЕНИЕ: Сигнатуры функций приведены в соответствие с
# DI-контейнером `Deps` для корректной работы с центральным навигатором.
# ===============================================================
import logging
import asyncio
from typing import Union

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.utils.dependencies import Deps
from bot.utils.plotting import generate_fng_image
from bot.utils.formatters import format_halving_info, format_network_status
from bot.utils.ui_helpers import show_main_menu_from_callback

router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- ОБРАБОТЧИКИ ДЛЯ РАЗНЫХ ТИПОВ РЫНОЧНЫХ ДАННЫХ ---

@router.callback_query(F.data == "nav:fear_greed")
async def handle_fear_greed_menu(call: CallbackQuery, deps: Deps):
    """
    Обрабатывает запрос на получение Индекса страха и жадности.
    Генерирует и отправляет изображение.
    """
    await call.message.delete()
    temp_message = await call.message.answer("⏳ Получаю индекс и рисую график...")

    index = await deps.market_data_service.get_fear_and_greed_index()
    if not index:
        await temp_message.edit_text("❌ Не удалось получить Индекс страха и жадности.", reply_markup=get_main_menu_keyboard())
        return

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
async def handle_market_data_navigation(call: CallbackQuery, deps: Deps):
    """
    Универсальный обработчик для кнопок "Халвинг" и "Статус BTC".
    """
    action = call.data.split(':')[1]
    
    if action == "fear_greed":
        await call.answer()
        return

    text = "⏳ Загружаю данные..."
    await call.message.edit_text(text)
    
    response_text = "❌ Произошла ошибка при загрузке данных."

    if action == "halving":
        halving_info = await deps.market_data_service.get_halving_info()
        if halving_info:
            response_text = format_halving_info(halving_info)
    
    elif action == "btc_status":
        network_status = await deps.market_data_service.get_btc_network_status()
        if network_status:
            response_text = format_network_status(network_status)

    await call.message.edit_text(response_text, reply_markup=get_main_menu_keyboard())