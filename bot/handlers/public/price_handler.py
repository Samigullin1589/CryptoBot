# src/bot/handlers/public/price_handler.py
from __future__ import annotations

import asyncio
from typing import List, Optional, Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from bot.keyboards.callback_factories import MenuCallback

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
    except Exception as e:
        logger.debug(f"Failed to call {method}: {e}")
        return None


async def _get_price_any(deps, symbol: str, quote: str = "USD") -> Optional[float]:
    """Универсальный метод получения цены из разных сервисов"""
    symbol_u, quote_u = symbol.upper(), quote.upper()
    
    # Маппинг символов в coin_id для CoinGecko
    SYMBOL_TO_COIN_ID = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "USDT": "tether",
        "BNB": "binancecoin",
        "SOL": "solana",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "TRX": "tron",
        "MATIC": "matic-network",
        "LTC": "litecoin",
        "AVAX": "avalanche-2",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "ATOM": "cosmos",
    }
    
    # Пробуем через price_service
    price_service = getattr(deps, "price_service", None)
    if price_service:
        coin_id = SYMBOL_TO_COIN_ID.get(symbol_u)
        if coin_id:
            try:
                price = await price_service.get_price(coin_id)
                if price is not None:
                    return float(price)
            except Exception as e:
                logger.debug(f"price_service.get_price failed for {coin_id}: {e}")
    
    # Пробуем через market_data_service
    market_service = getattr(deps, "market_data_service", None)
    if market_service:
        coin_id = SYMBOL_TO_COIN_ID.get(symbol_u)
        if coin_id:
            try:
                prices = await market_service.get_prices([coin_id])
                if prices and coin_id in prices:
                    price = prices[coin_id]
                    if price is not None:
                        return float(price)
            except Exception as e:
                logger.debug(f"market_data_service.get_prices failed for {coin_id}: {e}")
    
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
    rows.append([InlineKeyboardButton(text=f"🔄 Обновить", callback_data=f"price:refresh:{quote}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_price_menu(message_or_call, deps, quote: str = "USD"):
    """Показывает меню с ценами топовых криптовалют"""
    top_symbols = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "TRX", "MATIC", "LTC", "AVAX"]
    
    text = f"💰 <b>Цены криптовалют в {quote}</b>\n\nВыберите монету для просмотра цены:"
    keyboard = _kb_top(top_symbols, quote)
    
    if isinstance(message_or_call, CallbackQuery):
        try:
            await message_or_call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await message_or_call.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message_or_call.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("price"))
async def cmd_price(message: Message, deps) -> None:
    """Обработчик команды /price"""
    parts = (message.text or "").split()
    
    if len(parts) == 1:
        # Просто /price - показываем меню
        await show_price_menu(message, deps)
        return
    
    symbol = parts[1].upper()
    quote = parts[2].upper() if len(parts) >= 3 else "USD"

    price = await _get_price_any(deps, symbol, quote)
    if price is None:
        await message.answer(f"❌ Не удалось получить цену {symbol}/{quote}. Попробуйте позже.")
        return

    text = f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(price)}</code>"
    top_symbols = ["BTC", "ETH", "BNB", "SOL", "XRP"]
    await message.answer(text, parse_mode="HTML", reply_markup=_kb_top(top_symbols, quote))


@router.callback_query(MenuCallback.filter(F.action == "price"))
async def menu_price_handler(call: CallbackQuery, deps) -> None:
    """Обработчик кнопки 'Курс' из главного меню"""
    await call.answer()
    await show_price_menu(call, deps)


@router.callback_query(F.data.startswith("price:"))
async def cb_price(call: CallbackQuery, deps) -> None:
    """Обработчик callback для выбора конкретной монеты"""
    await call.answer()
    
    if not call.data:
        return
    
    parts = call.data.split(":")
    
    if len(parts) < 2:
        await call.answer("Некорректный запрос", show_alert=True)
        return

    if parts[1] == "refresh":
        quote = parts[2].upper() if len(parts) > 2 else "USD"
        await show_price_menu(call, deps, quote)
        return

    symbol = parts[1].upper()
    quote = parts[2].upper() if len(parts) > 2 else "USD"
    
    price = await _get_price_any(deps, symbol, quote)
    if price is None:
        await call.answer(f"⚠️ Не удалось получить цену {symbol}", show_alert=True)
        return
    
    text = f"💰 <b>{symbol}/{quote}</b>\n\n<code>${_fmt_price(price)}</code>"
    
    try:
        await call.message.edit_text(
            text, 
            parse_mode="HTML", 
            reply_markup=call.message.reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing price message: {e}")