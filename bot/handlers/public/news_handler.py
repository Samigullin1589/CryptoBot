# =================================================================================
# Файл: bot/handlers/public/news_handler.py (ИНТЕГРИРОВАННЫЙ - РЕФАКТОРИНГ)
# Описание: Обработчик для раздела новостей.
# ИСПРАВЛЕНИЕ: Добавлен фильтр MenuCallback для прямого отклика на кнопку меню.
# =================================================================================
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hlink

from bot.keyboards.news_keyboards import get_news_sources_keyboard
from bot.keyboards.callback_factories import NewsCallback, MenuCallback
from bot.utils.dependencies import Deps

router = Router(name="news_handler_router")
logger = logging.getLogger(__name__)

@router.callback_query(MenuCallback.filter(F.action == "news"))
async def handle_news_menu_start(call: CallbackQuery, deps: Deps):
    """Точка входа в раздел новостей из главного меню."""
    sources = deps.news_service.get_all_sources()
    text = "Выберите источник, чтобы прочитать последние новости:"
    await call.message.edit_text(text, reply_markup=get_news_sources_keyboard(sources))
    await call.answer()

@router.callback_query(NewsCallback.filter(F.action == "get_feed"))
async def get_news_feed(call: CallbackQuery, callback_data: NewsCallback, deps: Deps):
    """Получает и отображает новости из источника, выбранного пользователем."""
    source_key = callback_data.source_key
    all_sources = deps.news_service.get_all_sources()
    source_name = all_sources.get(source_key, "Неизвестный источник")
    
    await call.answer(f"Загружаю новости из {source_name}...")
    articles = await deps.news_service.get_latest_news(source_key)
    
    if not articles:
        await call.message.edit_text(
            f"❌ Не удалось загрузить новости из «{source_name}».",
            reply_markup=get_news_sources_keyboard(all_sources)
        )
        return

    response_lines = [f"<b>Свежие новости из {source_name}:</b>\n"]
    for i, article in enumerate(articles, 1):
        response_lines.append(f"{i}. {hlink(article.title, article.url)}")
    response_text = "\n".join(response_lines)
    
    await call.message.edit_text(
        response_text,
        reply_markup=get_news_sources_keyboard(all_sources),
        disable_web_page_preview=True
    )