# ======================================================================================
# File: bot/handlers/news_handler.py
# Version: "Distinguished Engineer" — Aug 17, 2025
# Description:
#   /news с кешем и постраничной навигацией.
#   Исправления: безопасные фолбэки к методам NewsService, всегда есть callback.answer()
# ======================================================================================

from __future__ import annotations

import asyncio
from typing import List, Dict, Any, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

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
    except Exception:
        return None


async def _get_items(deps) -> List[Dict[str, Any]]:
    svc = getattr(deps, "news_service", None)
    if not svc:
        return []
    # популярные варианты API
    calls = [
        ("get_cached", {}),
        ("get_all_latest_news", {}),
        ("get_latest", {"limit": 50}),
        ("fetch", {"limit": 50}),
        ("headlines", {"limit": 50}),
    ]
    for name, kw in calls:
        data = await _try_call(svc, name, **kw)
        if not data:
            continue
        items: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            data = data.get("items") or data.get("news") or data.get("results") or []
        if isinstance(data, (list, tuple)):
            for it in data:
                if isinstance(it, dict):
                    items.append(it)
        if items:
            return items
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


@router.callback_query(F.data.startswith("news:")))
async def cb_news(call: CallbackQuery, deps) -> None:
    await call.answer()
    data = (call.data or "").split(":")
    items = await _get_items(deps)

    if len(data) >= 3 and data[1] == "page":
        try:
            page = max(0, int(data[2]))
        except ValueError:
            page = 0
        await call.message.edit_text(
            _render(items, page=page),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_page_kb(page),
        )  # type: ignore[union-attr]
        return

    if len(data) >= 2 and data[1] == "refresh":
        await call.message.edit_text(
            _render(items, page=0),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_page_kb(0),
        )  # type: ignore[union-attr]
        return

    # неизвестное действие — просто перерисуем первую страницу
    await call.message.edit_text(
        _render(items, page=0),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_page_kb(0),
    )  # type: ignore[union-attr]