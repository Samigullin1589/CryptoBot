# src/bot/handlers/public/text_handler.py
from __future__ import annotations

import re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

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


@router.message(Command("ask"))
async def cmd_ask(message: Message, deps) -> None:
    """Обработчик команды /ask для вопросов к AI"""
    try:
        # Получаем текст после команды
        command_text = message.text or ""
        question = command_text.replace("/ask", "", 1).strip()
        
        if not question:
            await message.answer(
                "💡 <b>Как использовать /ask:</b>\n\n"
                "Просто напишите вопрос после команды:\n"
                "<code>/ask Что такое биткоин?</code>\n\n"
                "Я отвечу на любые вопросы о криптовалютах! 🤖",
                parse_mode="HTML"
            )
            return
        
        # Отправляем индикатор "печатает"
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Получаем AI сервис
        ai_service = getattr(deps, "ai_content_service", None)
        if not ai_service:
            await message.answer(
                "❌ AI сервис временно недоступен. Попробуйте позже.",
                parse_mode="HTML"
            )
            return
        
        # Генерируем ответ
        response = await ai_service.generate_answer(
            question=question,
            context="Ты - помощник по криптовалютам. Отвечай кратко и понятно."
        )
        
        if not response:
            await message.answer(
                "❌ Не удалось получить ответ. Попробуйте переформулировать вопрос.",
                parse_mode="HTML"
            )
            return
        
        # Отправляем ответ
        await message.answer(
            f"🤖 <b>Ответ:</b>\n\n{response}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.exception(f"Error in /ask command: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке запроса. Попробуйте позже.",
            parse_mode="HTML"
        )


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
        await message.answer(
            f"❌ Неизвестная монета: {symbol}. Используйте /help для списка поддерживаемых монет.", 
            parse_mode="HTML"
        )
        return

    try:
        p = await deps.price_service.get_price(coin_id)
        if p is None:
            await message.answer(
                "❌ Не удалось получить цену. Попробуйте позже.", 
                parse_mode="HTML"
            )
            return

        await message.answer(
            f"<b>{symbol}/USD</b>: <code>${p:,.2f}</code>", 
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        await message.answer(
            "❌ Ошибка получения цены. Попробуйте позже.", 
            parse_mode="HTML"
        )