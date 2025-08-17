# ======================================================================================
# File: bot/handlers/price_handler.py
# Version: "Distinguished Engineer" — Aug 17, 2025
# Description:
#   /price [SYMBOL] [QUOTE] + быстрые кнопки.
#   Универсальный фолбэк к твоим сервисам, чтобы не было «Нет данных».
# ======================================================================================

from __future__ import annotations

import asyncio
from typing import List, Optional, Any

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


async def _get_price_any(deps, symbol: str, quote: str) -> Optional[float]:
    symbol_u, quote_u = symbol.upper(), quote.upper()
    svc_candidates = [getattr(deps, "price_service", None), getattr(deps, "market_data_service", None)]
    methods = [
        (("get_price",), {"symbol": symbol_u, "vs": quote_u}),
        (("get_price",), {"ticker": symbol_u, "vs": quote_u}),
        (("get_spot", "spot", "price"), {"symbol": symbol_u, "vs": quote_u}),
        (("get_ticker", "ticker"), {"symbol": symbol_u}),
        (("fetch_price", "fetch_spot"), {"symbol": symbol_u, "vs": quote_u}),
        (("get_pair",), {"pair": f"{symbol_u}{quote_u}"}),
    ]
    for svc in svc_candidates:
        for names, kw in methods:
            for name in names:
                val = await _try_call(svc, name, **kw)
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, dict):
                    for k in ("price", "spot", "last", "close", "value"):
                        v = val.get(k)
                        if isinstance(v, (int, float)):
                            return float(v)
                    cell = (val.get(symbol_u) or val.get(symbol_u.lower()))
                    if isinstance(cell, dict):
                        v = cell.get(quote_u) or cell.get(quote_u.lower())
                        if isinstance(v, (int, float)):
                            return float(v)

    # через coin_id
    cls = getattr(deps, "coin_list_service", None)
    mds = getattr(deps, "market_data_service", None)
    if cls and mds:
        for m in ("find_coin_id", "get_id_by_ticker", "get_id_by_symbol", "resolve_id", "by_ticker"):
            coin_id = await _try_call(cls, m, symbol_u)
            if isinstance(coin_id, str) and coin_id:
                for name in ("get_price_by_id", "price_by_id", "get_spot_by_id", "fetch_price_by_id"):
                    val = await _try_call(mds, name, coin_id=coin_id, vs=quote_u)
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        v = (val.get("price") or val.get("spot") or val.get("last"))
                        if isinstance(v, (int, float)):
                            return float(v)
                break
    return None


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
    parts = (message.text or "").split()
    symbol = parts[1].upper() if len(parts) >= 2 else "BTC"
    default_quote = getattr(getattr(deps.settings, "price_service", object()), "default_quote", "USDT")
    quote = parts[2].upper() if len(parts) >= 3 else str(default_quote).upper()

    price = await _get_price_any(deps, symbol, quote)
    if price is None:
        await message.answer(f"❌ Не удалось получить цену {symbol}/{quote}. Попробуйте позже.")
        return

    text = f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(price)}</code>"
    top = await _try_call(getattr(deps, "price_service", None), "_get_top_symbols") or ["BTC", "ETH", "BNB", "SOL", "XRP"]
    await message.answer(text, parse_mode="HTML", reply_markup=_kb_top(list(top), quote))


@router.callback_query(F.data.startswith("price:"))
async def cb_price(call: CallbackQuery, deps) -> None:
    await call.answer()
    parts = (call.data or "").split(":")
    if len(parts) < 3:
        await call.message.answer("Некорректный запрос.")  # type: ignore[union-attr]
        return

    if parts[1] == "refresh":
        quote = (parts[2] if len(parts) > 2 else "USDT").upper()
        top = await _try_call(getattr(deps, "price_service", None), "_get_top_symbols") or ["BTC", "ETH", "BNB", "SOL", "XRP"]
        await call.message.edit_reply_markup(reply_markup=_kb_top(list(top), quote))  # type: ignore[union-attr]
        return

    symbol = parts[1].upper()
    quote = (parts[2] if len(parts) > 2 else "USDT").upper()
    price = await _get_price_any(deps, symbol, quote)
    if price is None:
        await call.message.edit_text("⚠️ Нет данных сейчас. Повторите позже.")  # type: ignore[union-attr]
        return
    text = f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(price)}</code>"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=call.message.reply_markup)  # type: ignore[union-attr]