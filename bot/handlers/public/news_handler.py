# src/bot/handlers/public/news_handler.py
from __future__ import annotations

import asyncio
from typing import List, Dict, Any, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

router = Router(name="news_public")

PAGE_SIZE = 8


def _page_kb(page: int) -> InlineKeyboardMarkup:
    prev_btn = InlineKeyboardButton(text="⬅️ Назад", callback_data=f"news:page:{max(0, page-1)}")
    next_btn = InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"news:page:{page+1}")
    refresh_btn = InlineKeyboardButton(text="🔄 Обновить", callback_data="news:refresh")
    return InlineKeyboardMarkup(inline_keyboard=[[prev_btn, next_btn], [refresh_btn]])


def _render(items: List[Dict[str, Any]], page: int) -> str:
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    if not chunk:
        return "Пока новостей нет."
    lines = [f"<b>📰 Крипто-новости — страница {page+1}</b>", ""]
    for it in chunk:
        title = (it.get("title") or it.get("headline") or "").strip()
        url = (it.get("url") or it.get("link") or "").strip()
        src = (it.get("src") or it.get("source") or "").strip()
        if url and title:
            lines.append(f"• <a href=\"{url}\">{title}</a> <i>({src})</i>")
        elif title:
            lines.append(f"• {title}")
    lines.append("")
    lines.append(f"<i>Показано {len(chunk)} из {len(items)}.</i>")
    return "\n".join(lines)


async def _try_call(obj: Any, method: str, *args, **kwargs) -> Optional[Any]:
    if not obj or not hasattr(obj, method):
        return None
    fn = getattr(obj, method)
    try:
        res = fn(*args, **kwargs)
        if asyncio.iscoroutine(res):
            res = await res
        return res
    except Exception as e:
        logger.debug(f"Failed to call {method}: {e}")
        return None


async def _get_items(deps) -> List[Dict[str, Any]]:
    svc = getattr(deps, "news_service", None)
    if not svc:
        return []
    
    try:
        data = await svc.get_all_latest_news(limit=50)
        if data:
            items: List[Dict[str, Any]] = []
            for article in data:
                if hasattr(article, 'model_dump'):
                    items.append(article.model_dump())
                elif isinstance(article, dict):
                    items.append(article)
            return items
    except Exception as e:
        logger.error(f"Error getting news: {e}")
    
    return []


@router.message(Command("news"))
async def cmd_news(message: Message, deps) -> None:
    items = await _get_items(deps)
    await message.answer(
        _render(items, page=0),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_page_kb(0),
    )


@router.callback_query(F.data.startswith("news:"))
async def cb_news(call: CallbackQuery, deps) -> None:
    await call.answer()
    
    if not call.message:
        return
    
    data = (call.data or "").split(":")
    items = await _get_items(deps)
    page = 0

    if len(data) >= 3 and data[1] == "page":
        try:
            page = max(0, int(data[2]))
        except ValueError:
            page = 0
    elif len(data) >= 2 and data[1] == "refresh":
        page = 0
    
    new_text = _render(items, page=page)
    new_markup = _page_kb(page)
    
    # Проверяем, изменилось ли содержимое
    try:
        await call.message.edit_text(
            new_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=new_markup,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Сообщение не изменилось, это не ошибка
            logger.debug("Message content unchanged, skipping edit")
        else:
            logger.error(f"Error editing message: {e}")
            raise