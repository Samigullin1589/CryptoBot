# ======================================================================================
# File: bot/handlers/news_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   /news with cached items (NewsService). Paged inline navigation.
# ======================================================================================

from __future__ import annotations

from typing import List, Dict, Any

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
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        src = it.get("src") or ""
        lines.append(f"• <a href=\"{url}\">{title}</a> <i>({src})</i>")
    lines.append("")
    lines.append(f"<i>Показано {len(chunk)} из {len(items)}.</i>")
    return "\n".join(lines)


async def _get_items(deps) -> List[Dict[str, Any]]:
    svc = deps.news_service  # type: ignore[attr-defined]
    items = await svc.get_cached()
    if not items:
        items = await svc.get_all_latest_news()
    return items or []


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
        await call.answer()
        return

    if data[1] == "refresh":
        await call.message.edit_text(
            _render(items, page=0),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_page_kb(0),
        )  # type: ignore[union-attr]
        await call.answer("Обновлено.")
        return

    await call.answer("Неизвестное действие.")