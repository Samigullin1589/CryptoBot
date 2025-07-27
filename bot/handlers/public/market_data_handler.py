# ===============================================================
# Файл: bot/handlers/public/market_data_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчики для запросов рыночных данных.
# Использует единый динамический обработчик для масштабируемости.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.market_data_service import MarketDataService
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id
from bot.utils.plotting import generate_fng_image

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("menu_market_"))
@router.message(F.text.in_({"😱 Индекс Страха", "⏳ Халвинг", "📡 Статус BTC"}))
async def handle_market_data_request(update: Union[CallbackQuery, Message], market_data_service: MarketDataService, admin_service: AdminService):
    """
    Единый обработчик для всех запросов рыночных данных.
    """
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        action = update.data.removeprefix("menu_market_")
        await update.answer()
    else:
        # Преобразуем текст кнопки в action
        action_map = {
            "😱 Индекс Страха": "fear_greed",
            "⏳ Халвинг": "halving",
            "📡 Статус BTC": "btc_status"
        }
        action = action_map.get(update.text)

    await admin_service.track_command_usage(f"Рыночные данные: {action}")
    
    # --- Индекс Страха и Жадности ---
    if action == "fear_greed":
        temp_message = await message.answer("⏳ Получаю индекс и рисую график...")
        index = await market_data_service.get_fear_and_greed_index()
        if not index:
            await temp_message.edit_text("Не удалось получить индекс.", reply_markup=get_main_menu_keyboard())
            return
        
        value = int(index.get('value', 50))
        classification = index.get('value_classification', 'Neutral')
        image_bytes = await message.loop.run_in_executor(None, generate_fng_image, value, classification)
        
        await temp_message.delete()
        await message.answer_photo(
            BufferedInputFile(image_bytes, "fng.png"),
            caption=f"😱 <b>Индекс страха и жадности: {value} - {classification}</b>",
            reply_markup=get_main_menu_keyboard()
        )

    # --- Халвинг и Статус BTC (текстовые ответы) ---
    else:
        temp_message = await message.answer("⏳ Получаю данные...")
        if action == "halving":
            text = await market_data_service.get_halving_info()
        elif action == "btc_status":
            text = await market_data_service.get_btc_network_status()
        else:
            text = "Неизвестное действие."
            
        await temp_message.edit_text(text, reply_markup=get_main_menu_keyboard())
