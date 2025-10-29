# src/bot/handlers/public/text_handler.py
from __future__ import annotations

import re
from aiogram import Router
from aiogram.types import Message

router = Router(name="text_public")

_PAIR_RE = re.compile(r"^\s*([a-zA-Z]{2,10})\s*[/\s,-]?\s*([a-zA-Z]{2,10})?\s*$")

# Маппинг тикеров в CoinGecko ID
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


def _norm_symbol(s: str) -> str:
    return s.strip().upper()


@router.message()
async def on_text(message: Message, deps) -> None:
    text = (message.text or "").strip()

    if text.lower() in ("news", "новости", "📰"):
        from bot.handlers.public.news_handler import cmd_news
        await cmd_news(message, deps)
        return

    m = _PAIR_RE.match(text)
    if not m:
        return

    symbol = _norm_symbol(m.group(1))
    coin_id = SYMBOL_TO_COIN_ID.get(symbol)
    
    if not coin_id:
        await message.answer(f"❌ Неизвестная монета: {symbol}. Используйте /help для списка поддерживаемых монет.", parse_mode="HTML")
        return

    p = await deps.price_service.get_price(coin_id)
    if p is None:
        await message.answer("❌ Не удалось получить цену. Попробуйте позже.", parse_mode="HTML")
        return

    await message.answer(f"<b>{symbol}/USD</b>: <code>${p:,.2f}</code>", parse_mode="HTML")