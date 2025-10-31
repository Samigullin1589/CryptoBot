# src/bot/handlers/public/news_handler.py
from __future__ import annotations

from typing import List, Dict, Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.keyboards.callback_factories import NewsCallback

router = Router(name="news_public")

PAGE_SIZE = 5


def get_news_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для навигации по новостям"""
    buttons = []
    
    if page > 0:
        buttons.append([
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=NewsCallback(action="page", source_key=str(page - 1)).pack()
            ),
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=NewsCallback(action="page", source_key=str(page + 1)).pack()
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=NewsCallback(action="page", source_key=str(page + 1)).pack()
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=NewsCallback(action="refresh", source_key=None).pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def render_news(articles: List[Any], page: int) -> str:
    """Форматирует новости для отображения"""
    if not articles:
        return "📰 <b>Новости</b>\n\nПока новостей нет."
    
    start = page * PAGE_SIZE
    chunk = articles[start:start + PAGE_SIZE]
    
    if not chunk:
        return "📰 <b>Новости</b>\n\nБольше новостей нет."
    
    lines = [f"📰 <b>Крипто-новости — страница {page + 1}</b>\n"]
    
    for article in chunk:
        if hasattr(article, 'title'):
            title = article.title
            url = article.url
            source = article.source
        else:
            title = article.get('title', 'Без заголовка')
            url = article.get('url', '')
            source = article.get('source', '')
        
        if url and title:
            lines.append(f"• <a href=\"{url}\">{title}</a> <i>({source})</i>")
        elif title:
            lines.append(f"• {title}")
    
    lines.append(f"\n<i>Показано {len(chunk)} из {len(articles)}</i>")
    
    return "\n".join(lines)


async def get_news_articles(deps) -> List[Any]:
    """Получает новости из news_service"""
    try:
        news_service = deps.news_service()
        articles = await news_service.get_all_latest_news(limit=50)
        return articles if articles else []
    except Exception as e:
        logger.error(f"Error getting news: {e}")
    return []


@router.message(Command("news"))
async def cmd_news(message: Message, deps) -> None:
    """Обработчик команды /news"""
    articles = await get_news_articles(deps)
    text = render_news(articles, 0)
    await message.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_news_keyboard(0)
    )


@router.callback_query(NewsCallback.filter(F.action == "sources"))
async def news_menu_handler(call: CallbackQuery, deps) -> None:
    """Обработчик открытия меню новостей из главного меню"""
    await call.answer()
    
    articles = await get_news_articles(deps)
    text = render_news(articles, 0)
    
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_news_keyboard(0)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error editing message: {e}")


@router.callback_query(NewsCallback.filter(F.action == "page"))
async def news_page_handler(call: CallbackQuery, deps, callback_data: NewsCallback) -> None:
    """Обработчик пагинации новостей"""
    await call.answer()
    
    try:
        page = int(callback_data.source_key) if callback_data.source_key else 0
    except (ValueError, TypeError):
        page = 0
    
    articles = await get_news_articles(deps)
    text = render_news(articles, page)
    
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_news_keyboard(page)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error editing message: {e}")


@router.callback_query(NewsCallback.filter(F.action == "refresh"))
async def news_refresh_handler(call: CallbackQuery, deps) -> None:
    """Обновляет новости"""
    await call.answer("🔄 Обновление...")
    await news_menu_handler(call, deps)