import asyncio
import logging
import re
from typing import Any, Callable, Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message

from bot.filters.not_command_filter import NotCommandFilter
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

router = Router(name="public_common")


# ------------------------- Вспомогательные утилиты -------------------------

_COIN_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,19}$")


def _looks_like_coin_token(text: str) -> bool:
    t = text.strip()
    if not t or " " in t:
        return False
    return bool(_COIN_TOKEN_RE.match(t))


async def _maybe_call(func, *args, **kwargs):
    res = func(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


async def _resolve_coin(deps: Deps, query: str) -> Tuple[Optional[str], Optional[str]]:
    cls = getattr(deps, "coin_list_service", None)
    candidates = [
        ("resolve_query", {"query": query}),
        ("resolve", {"query": query}),
        ("get_coin_by_query", {"query": query}),
        ("find", {"text": query}),
        ("get", {"query": query}),
    ]
    for name, kwargs in candidates:
        if cls and hasattr(cls, name):
            try:
                obj = await _maybe_call(getattr(cls, name), **kwargs)
                if not obj:
                    continue
                coin_id = getattr(obj, "id", None) or (obj.get("id") if isinstance(obj, dict) else None)
                symbol = getattr(obj, "symbol", None) or (obj.get("symbol") if isinstance(obj, dict) else None)
                symbol = symbol or getattr(obj, "ticker", None) or (obj.get("ticker") if isinstance(obj, dict) else None)
                if coin_id or symbol:
                    return (str(coin_id) if coin_id else None), (str(symbol).upper() if symbol else None)
            except Exception as e:
                logger.debug("coin_list_service.%s failed: %s", name, e)
    return None, query.upper()


async def _fetch_usd_price(deps: Deps, symbol: str) -> Optional[float]:
    ps = getattr(deps, "price_service", None)
    mds = getattr(deps, "market_data_service", None)

    ps_candidates = [
        ("get_price", {"symbol": symbol, "fiat": "usd"}),
        ("get_price", {"coin": symbol, "fiat": "usd"}),
        ("get_prices", {"symbols": [symbol], "fiat": "usd"}),
        ("fetch_prices", {"symbols": [symbol], "fiat": "usd"}),
    ]
    for name, kwargs in ps_candidates:
        if ps and hasattr(ps, name):
            try:
                res = await _maybe_call(getattr(ps, name), **kwargs)
                if isinstance(res, (int, float)):
                    return float(res)
                if isinstance(res, dict):
                    val = res.get(symbol) or res.get(symbol.upper()) or res.get(symbol.lower())
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        return float(val.get("usd") or val.get("USD") or val.get("price") or 0) or None
            except Exception as e:
                logger.debug("price_service.%s failed: %s", name, e)

    mds_candidates = [
        ("get_price", {"symbol": symbol, "fiat": "usd"}),
        ("get_prices", {"symbols": [symbol], "fiat": "usd"}),
        ("fetch_price", {"symbol": symbol, "fiat": "usd"}),
    ]
    for name, kwargs in mds_candidates:
        if mds and hasattr(mds, name):
            try:
                res = await _maybe_call(getattr(mds, name), **kwargs)
                if isinstance(res, (int, float)):
                    return float(res)
                if isinstance(res, dict):
                    val = res.get(symbol) or res.get(symbol.upper()) or res.get(symbol.lower())
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        return float(val.get("usd") or val.get("USD") or val.get("price") or 0) or None
            except Exception as e:
                logger.debug("market_data_service.%s failed: %s", name, e)

    return None


async def _reply_with_price(message: Message, symbol: str, price_usd: float) -> None:
    text = f"Курс {symbol}: ${price_usd:,.2f} (USD)"
    try:
        await message.answer(text)
    except Exception as e:
        logger.error("Failed to send price reply: %s", e, exc_info=True)


def _user_in_price_context(deps: Deps, user_id: int) -> bool:
    us = getattr(deps, "user_state_service", None)
    if not us:
        return False
    for name in ("get_current_section", "get_section", "get_user_section", "get_mode"):
        if hasattr(us, name):
            try:
                section = getattr(us, name)(user_id)
                if asyncio.iscoroutine(section):
                    return False
                section_str = (str(section) if section is not None else "").lower()
                if section_str in {"price", "prices", "курс", "курсы", "market_price"}:
                    return True
            except Exception:
                pass
    return False


def _extract_price_query(text: str) -> Optional[str]:
    t = text.strip()
    if _looks_like_coin_token(t):
        return t
    m = re.search(r"(?:^|\s)(?:курс|price|\$)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-]{0,19})", t, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ------------------------------ Обработчик ------------------------------

# ВАЖНО: добавлен NotCommandFilter(), чтобы /start и другие команды не попадали сюда
@router.message(F.text, NotCommandFilter())
async def handle_text_for_ai(message: Message, deps: Deps) -> None:
    """
    Для обычного текста:
      1) Перехватываем «ценовые» запросы и отвечаем курсом монеты.
      2) Остальное — передаём AI-консультанту.
    """
    user_text = (message.text or "").strip()

    in_price_ctx = _user_in_price_context(deps, message.from_user.id if message.from_user else 0)
    price_query = _extract_price_query(user_text)

    if in_price_ctx or price_query:
        query = price_query or user_text
        coin_id, symbol = await _resolve_coin(deps, query)
        symbol_for_fetch = symbol or (coin_id or "").upper()
        if symbol_for_fetch:
            price = await _fetch_usd_price(deps, symbol_for_fetch)
            if price is not None:
                await _reply_with_price(message, symbol_for_fetch, price)
                return
            else:
                try:
                    await message.answer("😕 Не удалось получить цену для указанной монеты.")
                except Exception:
                    pass
                return
        else:
            try:
                await message.answer("😕 Монета не распознана. Попробуйте, например: BTC, ETH, ALEO.")
            except Exception:
                pass
            return

    # Остальное — AI-консультант
    history_provider = getattr(deps, "history_service", None)
    history = None
    if history_provider and hasattr(history_provider, "get_history_for_user"):
        try:
            h = history_provider.get_history_for_user(message.from_user.id if message.from_user else 0)
            if asyncio.iscoroutine(h):
                h = await h
            history = h
        except Exception:
            history = None

    try:
        ai_answer = await deps.ai_content_service.get_consultant_answer(user_text, history)
        ai_answer = ai_answer or "Не удалось получить ответ от AI."
        await message.answer(
            "Ваш вопрос:\n«" + user_text + "»\n\nОтвет AI-Консультанта:\n" + ai_answer
        )
    except Exception as e:
        logger.error("AI answer failed: %s", e, exc_info=True)
        try:
            await message.answer("Произошла ошибка при обращении к AI.")
        except Exception:
            pass