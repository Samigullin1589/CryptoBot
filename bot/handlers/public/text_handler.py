# ======================================================================================
# File: bot/handlers/text_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Smart free-text parsing:
#     • "btc" -> BTC/USDT
#     • "btc usd" -> BTC/USD or BTC/USDT (quote normalized)
#     • "eth/usdt" -> ETH/USDT
#     • "news" / "новости" -> /news
# ======================================================================================

from __future__ import annotations

import re
from aiogram import Router
from aiogram.types import Message

router = Router(name="text_public")

_PAIR_RE = re.compile(r"^\s*([a-zA-Z]{2,10})\s*[/\s,-]?\s*([a-zA-Z]{2,10})?\s*$")


def _norm_symbol(s: str) -> str:
    return s.strip().upper()


def _norm_quote(q: str | None) -> str:
    if not q:
        return "USDT"
    q = q.strip().upper()
    # normalize common fiat shorthands
    return {"USD": "USDT", "RUB": "USDT", "EUR": "USDT"}.get(q, q)


@router.message()
async def on_text(message: Message, deps) -> None:
    text = (message.text or "").strip()

    # quick news alias
    if text.lower() in ("news", "новости", "📰"):
        from bot.handlers.news_handler import cmd_news
        await cmd_news(message, deps)  # reuse
        return

    m = _PAIR_RE.match(text)
    if not m:
        return  # пусть обрабатывают другие роутеры, если есть

    symbol = _norm_symbol(m.group(1))
    quote = _norm_quote(m.group(2) or getattr(getattr(deps.settings, "price_service", object()), "default_quote", "USDT"))

    p = await deps.price_service.get_price(symbol, quote)  # type: ignore[attr-defined]
    if p is None:
        await message.answer("❌ Не удалось распознать запрос или получить цену. Напишите <code>/help</code>.", parse_mode="HTML")
        return

    from bot.handlers.price_handler import _fmt_price  # reuse formatter
    await message.answer(f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(p)}</code>", parse_mode="HTML")