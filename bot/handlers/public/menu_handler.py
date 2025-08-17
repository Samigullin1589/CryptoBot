# ======================================================================================
# File: bot/handlers/menu_handler.py
# Version: "Distinguished Engineer" — Aug 17, 2025
# Description:
#   /menu и инлайн-меню с быстрыми действиями: цены, новости, справка.
#   Исправления:
#     • В каждом callback есть call.answer() -> нет «вечной загрузки»
#     • Цена/новости берутся через безопасные фолбэки (не зависит от точных имён методов)
# ======================================================================================

from __future__ import annotations

import asyncio
from typing import Any, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="menu_public")


def _menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="💱 Цена BTC", callback_data="menu:price:BTC:USDT"),
            InlineKeyboardButton(text="📰 Новости", callback_data="menu:news"),
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------- helpers (fallbacks) ----------------------------

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
    """
    Универсальный фетч цены: пробует популярные сигнатуры PriceService/MarketDataService.
    """
    candidates = [getattr(deps, "price_service", None), getattr(deps, "market_data_service", None)]
    tries = [
        (("get_price",), {"symbol": symbol, "vs": quote}),
        (("get_price",), {"ticker": symbol, "vs": quote}),
        (("get_spot", "spot", "price"), {"symbol": symbol, "vs": quote}),
        (("get_ticker", "ticker"), {"symbol": symbol}),
        (("fetch_price", "fetch_spot"), {"symbol": symbol, "vs": quote}),
    ]
    for svc in candidates:
        for names, kw in tries:
            for name in names:
                val = await _try_call(svc, name, **kw)
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, dict):
                    for k in ("price", "spot", "last", "close", "value"):
                        v = val.get(k)
                        if isinstance(v, (int, float)):
                            return float(v)
                    cell = (val.get(symbol) or val.get(symbol.upper()) or val.get(symbol.lower()))
                    if isinstance(cell, dict):
                        v = cell.get(quote) or cell.get(quote.upper()) or cell.get(quote.lower())
                        if isinstance(v, (int, float)):
                            return float(v)
    return None


def _fmt_price_local(p: float) -> str:
    if p >= 1000:
        return f"{p:,.2f}".replace(",", " ")
    if p >= 1:
        return f"{p:.2f}"
    if p >= 0.01:
        return f"{p:.4f}"
    return f"{p:.8f}".rstrip("0").rstrip(".")


# -------------------------------- handlers -----------------------------------

@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer("<b>Главное меню</b>", parse_mode="HTML", reply_markup=_menu_kb())


@router.callback_query(F.data == "menu:open")
async def cb_open(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text("<b>Главное меню</b>", parse_mode="HTML", reply_markup=_menu_kb())  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("menu:price:"))
async def cb_price_shortcut(call: CallbackQuery, deps) -> None:
    await call.answer()
    parts = (call.data or "").split(":")
    # ожидаем menu:price:SYMBOL:QUOTE
    if len(parts) < 4:
        await call.message.answer("Некорректный запрос цены.", parse_mode="HTML")  # type: ignore[union-attr]
        return
    _, _, symbol, quote = parts[:4]
    symbol = (symbol or "BTC").upper()
    quote = (quote or "USDT").upper()

    # пробуем локальный фолбэк
    price = await _get_price_any(deps, symbol, quote)
    if price is None:
        await call.message.answer("⚠️ Нет данных по цене сейчас. Повторите позже.", parse_mode="HTML")  # type: ignore[union-attr]
        return

    # если вдруг есть форматтер из price_handler — красиво переиспользуем
    try:
        from bot.handlers.price_handler import _fmt_price as _fmt_price_from_price  # type: ignore
        price_text = _fmt_price_from_price(price)
    except Exception:
        price_text = _fmt_price_local(price)

    text = f"<b>{symbol}/{quote}</b>: <code>{price_text}</code>"
    await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)  # type: ignore[union-attr]


@router.callback_query(F.data == "menu:news")
async def cb_news_shortcut(call: CallbackQuery, deps) -> None:
    await call.answer()
    # мягко используем рендер из news_handler, но без зависимости на него
    try:
        from bot.handlers.news_handler import _get_items, _render  # type: ignore
        items = await _get_items(deps)
        text = _render(items, page=0)
    except Exception:
        text = "Пока новостей нет."
    await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)  # type: ignore[union-attr]


@router.callback_query(F.data == "menu:help")
async def cb_help_shortcut(call: CallbackQuery) -> None:
    await call.answer()
    try:
        from bot.handlers.help_handler import HELP_TEXT  # type: ignore
        text = HELP_TEXT
    except Exception:
        text = "<b>Справка</b>\n/menu — главное меню\n/price — цена\n/news — новости"
    await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)  # type: ignore[union-attr]