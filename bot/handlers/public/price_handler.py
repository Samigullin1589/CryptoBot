# src/bot/handlers/public/price_handler.py
from __future__ import annotations

from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from bot.keyboards.callback_factories import PriceCallback

router = Router(name="price_public")

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


def get_price_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с топовыми криптовалютами"""
    buttons = []
    row = []
    symbols = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "TRX", "MATIC", "LTC", "AVAX"]
    
    for i, symbol in enumerate(symbols, 1):
        coin_id = SYMBOL_TO_COIN_ID.get(symbol, symbol.lower())
        row.append(InlineKeyboardButton(
            text=symbol,
            callback_data=PriceCallback(action="show", coin_id=coin_id).pack()
        ))
        if i % 3 == 0:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data=PriceCallback(action="refresh", coin_id="all").pack()
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_price_from_service(deps, coin_id: str) -> Optional[float]:
    """Получает цену из price_service"""
    try:
        price_service = getattr(deps, "price_service", None)
        if price_service:
            price = await price_service.get_price(coin_id)
            if price is not None:
                return float(price)
    except Exception as e:
        logger.error(f"Error getting price for {coin_id}: {e}")
    return None


@router.message(Command("price"))
async def cmd_price(message: Message, deps) -> None:
    """Обработчик команды /price"""
    text = "💰 <b>Цены криптовалют</b>\n\nВыберите монету для просмотра цены:"
    await message.answer(text, parse_mode="HTML", reply_markup=get_price_keyboard())


@router.callback_query(PriceCallback.filter(F.action == "open"))
async def price_menu_handler(call: CallbackQuery, deps) -> None:
    """Обработчик открытия меню цен из главного меню"""
    await call.answer()
    text = "💰 <b>Цены криптовалют</b>\n\nВыберите монету для просмотра цены:"
    
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_price_keyboard())
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await call.message.answer(text, parse_mode="HTML", reply_markup=get_price_keyboard())


@router.callback_query(PriceCallback.filter(F.action == "show"))
async def price_show_handler(call: CallbackQuery, deps, callback_data: PriceCallback) -> None:
    """Показывает цену конкретной монеты"""
    await call.answer()
    
    coin_id = callback_data.coin_id
    symbol = None
    for sym, cid in SYMBOL_TO_COIN_ID.items():
        if cid == coin_id:
            symbol = sym
            break
    
    if not symbol:
        symbol = coin_id.upper()
    
    price = await get_price_from_service(deps, coin_id)
    
    if price is None:
        await call.answer(f"⚠️ Не удалось получить цену {symbol}", show_alert=True)
        return
    
    text = f"💰 <b>{symbol}/USD</b>\n\n<code>${_fmt_price(price)}</code>"
    
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_price_keyboard())
    except Exception as e:
        logger.error(f"Error editing message: {e}")


@router.callback_query(PriceCallback.filter(F.action == "refresh"))
async def price_refresh_handler(call: CallbackQuery, deps) -> None:
    """Обновляет меню цен"""
    await call.answer("🔄 Обновление...")
    await price_menu_handler(call, deps)