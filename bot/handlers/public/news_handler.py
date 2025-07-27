# ===============================================================
# Файл: bot/handlers/public/news_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчик для команды получения новостей.
# ===============================================================
import logging
from typing import Union

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.news_service import NewsService
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "menu_news")
@router.message(F.text == "📰 Новости")
async def handle_news_menu(update: Union[CallbackQuery, Message], news_service: NewsService, admin_service: AdminService):
    """
    Обрабатывает запрос на получение последних новостей.
    """
    await admin_service.track_command_usage("📰 Новости")
    message, _ = await get_message_and_chat_id(update)
    
    temp_message = await message.answer("⏳ Загружаю новости...")

    news = await news_service.fetch_latest_news()
    if not news:
        await temp_message.edit_text("Не удалось загрузить новости.", reply_markup=get_main_menu_keyboard())
        return
        
    text = "📰 <b>Последние крипто-новости:</b>\n\n" + "\n\n".join(
        [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
        
    await temp_message.edit_text(text, disable_web_page_preview=True, reply_markup=get_main_menu_keyboard())
    
    if isinstance(update, CallbackQuery):
        await update.answer()
