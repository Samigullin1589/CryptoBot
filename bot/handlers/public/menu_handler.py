# ======================================================================================
# File: bot/handlers/menu_handler.py
# Version: "Distinguished Engineer" — Aug 17, 2025
# Description:
#   /menu и инлайн-меню с быстрыми действиями: цены, новости, справка.
#   • Всегда вызываем call.answer() -> нет «вечной загрузки»
#   • Универсальные фолбэки получения цены/новостей (совместимы с твоими сервисами)
#   • /menu показывает и большое главное меню, и быстрые шорткаты
# ======================================================================================

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.keyboards.main_menu import get_main_menu_keyboard

router = Router(name="menu_public")


def _menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="💱 Цена BTC", callback_data="menu:price:BTC:USDT"
            ),
            InlineKeyboardButton(text="📰 Новости", callback_data="menu:news"),
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------- helpers (fallbacks) ----------------------------


async def _try_call(obj: Any, method: str, *args, **kwargs) -> Any | None:
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


async def _get_price_any(deps, symbol: str, quote: str) -> float | None:
    """
    Универсальный фетч цены: пробует популярные сигнатуры PriceService/MarketDataService,
    умеет маппить тикер -> coin_id через CoinListService.
    """
    symbol_u, quote_u = symbol.upper(), quote.upper()
    svc_candidates = [
        getattr(deps, "price_service", None),
        getattr(deps, "market_data_service", None),
    ]
    tries = [
        (("get_price",), {"symbol": symbol_u, "vs": quote_u}),
        (("get_price",), {"ticker": symbol_u, "vs": quote_u}),
        (("get_spot", "spot", "price"), {"symbol": symbol_u, "vs": quote_u}),
        (("get_ticker", "ticker"), {"symbol": symbol_u}),
        (("fetch_price", "fetch_spot"), {"symbol": symbol_u, "vs": quote_u}),
        (("get_pair",), {"pair": f"{symbol_u}{quote_u}"}),
    ]
    for svc in svc_candidates:
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
                    cell = val.get(symbol_u) or val.get(symbol_u.lower())
                    if isinstance(cell, dict):
                        v = cell.get(quote_u) or cell.get(quote_u.lower())
                        if isinstance(v, (int, float)):
                            return float(v)

    # Через id
    cls = getattr(deps, "coin_list_service", None)
    mds = getattr(deps, "market_data_service", None)
    if cls and mds:
        # популярные методы маппинга тикера -> coin_id
        id_methods = (
            "find_coin_id",
            "get_id_by_ticker",
            "get_id_by_symbol",
            "resolve_id",
            "by_ticker",
        )
        coin_id = None
        for m in id_methods:
            coin_id = await _try_call(cls, m, symbol_u)
            if isinstance(coin_id, str) and coin_id:
                break
        if isinstance(coin_id, str) and coin_id:
            # популярные методы по id
            for name in (
                "get_price_by_id",
                "price_by_id",
                "get_spot_by_id",
                "fetch_price_by_id",
            ):
                val = await _try_call(mds, name, coin_id=coin_id, vs=quote_u)
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, dict):
                    v = (
                        val.get("price")
                        or val.get("spot")
                        or val.get("last")
                        or (
                            val.get(coin_id)
                            if isinstance(val.get(coin_id), (int, float))
                            else None
                        )
                    )
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
    # Большое основное меню
    await message.answer(
        "<b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_menu_keyboard()
    )
    # Быстрые кнопки под вторым сообщением
    await message.answer(
        "Быстрые действия:", parse_mode="HTML", reply_markup=_menu_kb()
    )


@router.callback_query(F.data == "menu:open")
async def cb_open(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "<b>Главное меню</b>", parse_mode="HTML", reply_markup=_menu_kb()
    )  # type: ignore[union-attr]


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

    price = await _get_price_any(deps, symbol, quote)
    if price is None:
        await call.message.answer(
            "⚠️ Нет данных по цене сейчас. Повторите позже.", parse_mode="HTML"
        )  # type: ignore[union-attr]
        return

    try:
        from bot.handlers.price_handler import _fmt_price as _fmt  # type: ignore

        price_text = _fmt(price)
    except Exception:
        price_text = _fmt_price_local(price)

    text = f"<b>{symbol}/{quote}</b>: <code>{price_text}</code>"
    await call.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)  # type: ignore[union-attr]


@router.callback_query(F.data == "menu:news")
async def cb_news_shortcut(call: CallbackQuery, deps) -> None:
    await call.answer()
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
