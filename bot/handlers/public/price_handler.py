# ======================================================================================
# File: bot/handlers/price_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Public price commands backed by PriceService:
#     • /price [SYMBOL] [QUOTE]  e.g., /price BTC USDT
#     • Quick buttons for top symbols
# ======================================================================================

from __future__ import annotations

from typing import List, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="price_public")


def _fmt_price(p: Optional[float]) -> str:
    if p is None:
        return "—"
    if p >= 1000:
        return f"{p:,.2f}".replace(",", " ")
    if p >= 1:
        return f"{p:.2f}"
    if p >= 0.01:
        return f"{p:.4f}"
    return f"{p:.8f}".rstrip("0").rstrip(".")


def _kb_top(symbols: List[str], quote: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, s in enumerate(symbols[:12], start=1):
        row.append(InlineKeyboardButton(text=s, callback_data=f"price:{s}:{quote}"))
        if i % 4 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=f"🔄 Обновить {quote}", callback_data=f"price:refresh:{quote}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("price"))
async def cmd_price(message: Message, deps) -> None:
    """
    /price [SYMBOL] [QUOTE]
    """
    parts = (message.text or "").split()
    symbol = parts[1].upper() if len(parts) >= 2 else "BTC"
    quote = parts[2].upper() if len(parts) >= 3 else getattr(getattr(deps.settings, "price_service", object()), "default_quote", "USDT").upper()

    p = await deps.price_service.get_price(symbol, quote)  # type: ignore[attr-defined]
    if p is None:
        await message.answer(f"❌ Не удалось получить цену {symbol}/{quote}. Попробуйте позже.")
        return

    text = f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(p)}</code>"
    # Подтянем топ-символы для быстрого запроса
    try:
        top = await deps.price_service._get_top_symbols()  # type: ignore[attr-defined]
    except Exception:
        top = ["BTC", "ETH", "BNB", "SOL", "XRP"]

    await message.answer(text, parse_mode="HTML", reply_markup=_kb_top(top, quote))


@router.callback_query(F.data.startswith("price:"))
async def cb_price(call: CallbackQuery, deps) -> None:
    parts = (call.data or "").split(":")
    if len(parts) < 3:
        await call.answer("Некорректный запрос.")
        return

    action, a, b = parts[1], parts[2], (parts[3] if len(parts) > 3 else "")
    if action == "refresh":
        quote = a
        try:
            top = await deps.price_service._get_top_symbols()  # type: ignore[attr-defined]
        except Exception:
            top = ["BTC", "ETH", "BNB", "SOL", "XRP"]
        await call.message.edit_reply_markup(reply_markup=_kb_top(top, quote))  # type: ignore[union-attr]
        await call.answer("Обновлено.")
        return

    # action == <SYMBOL>, b == quote
    symbol = action.upper()
    quote = a.upper()
    p = await deps.price_service.get_price(symbol, quote)  # type: ignore[attr-defined]
    if p is None:
        await call.answer("Нет данных.")
        return
    text = f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(p)}</code>"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=call.message.reply_markup)  # type: ignore[union-attr]
    await call.answer()