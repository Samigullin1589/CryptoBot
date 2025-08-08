# =================================================================================
# Файл: bot/handlers/public/news_handler.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Обрабатывает раздел "Новости" с пагинацией.
# =================================================================================
import logging
import math
from aiogram import F, Router
from aiogram.types import CallbackQuery
from bot.utils.dependencies import Deps
from bot.utils.formatters import format_news_list
from bot.keyboards.paginators import create_paginator_keyboard

router = Router(name=__name__)
logger = logging.getLogger(__name__)

NEWS_PER_PAGE = 5

@router.callback_query(F.data.in_({"nav:news", "news_page:0"}))
async def handle_news_list_start(call: CallbackQuery, deps: Deps):
    await handle_news_list_page(call, deps, page=0)

@router.callback_query(F.data.startswith("news_page:"))
async def handle_news_list_page_callback(call: CallbackQuery, deps: Deps):
    page = int(call.data.split(":")[1])
    await handle_news_list_page(call, deps, page)

async def handle_news_list_page(call: CallbackQuery, deps: Deps, page: int):
    await call.answer("Загружаю новости...")
    
    all_articles = await deps.news_service.get_latest_news()
    
    if not all_articles:
        await call.message.edit_text("Не удалось загрузить новости. Попробуйте позже.", reply_markup=create_paginator_keyboard(0, 1, 'news_page'))
        return

    total_pages = math.ceil(len(all_articles) / NEWS_PER_PAGE)
    start_index = page * NEWS_PER_PAGE
    end_index = start_index + NEWS_PER_PAGE
    articles_on_page = all_articles[start_index:end_index]

    text = format_news_list(articles_on_page, page, total_pages)
    keyboard = create_paginator_keyboard(page, total_pages, 'news_page')
    
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
