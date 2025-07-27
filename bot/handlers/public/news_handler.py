# ===============================================================
# Файл: bot/handlers/public/news_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Обрабатывает запросы на получение новостей.
# ===============================================================
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.news_service import NewsService
from bot.utils.formatters import format_news

# Инициализация роутера
router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "nav:news")
async def handle_news_menu(call: CallbackQuery, news_service: NewsService):
    """
    Обрабатывает запрос на получение новостей по нажатию на кнопку.
    """
    await call.message.edit_text("⏳ Загружаю свежие новости...")
    
    # Используем новый NewsService, который получает данные из разных источников
    news_articles = await news_service.get_latest_news()
    
    if not news_articles:
        text = "❌ Не удалось загрузить новости. Попробуйте позже."
        await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())
        await call.answer()
        return
        
    # Используем форматтер для создания красивого сообщения
    text = format_news(news_articles)
        
    await call.message.edit_text(
        text, 
        disable_web_page_preview=True, 
        reply_markup=get_main_menu_keyboard()
    )
    await call.answer()
