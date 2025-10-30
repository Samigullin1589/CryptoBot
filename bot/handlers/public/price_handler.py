# bot/handlers/public/price_handler.py
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger
import aiohttp

from bot.keyboards.callback_factories import PriceCallback
from bot.utils.dependencies import Deps

router = Router(name="price_public")

# Кэш цен с timestamp
_price_cache: Dict[str, tuple[float, datetime]] = {}
_CACHE_TTL = timedelta(seconds=60)

# Популярные монеты (СИМВОЛЫ -> coin_id для CoinGecko)
COIN_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
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
}

DEFAULT_SYMBOLS = list(COIN_MAP.keys())


def _fmt_price(p: Optional[float]) -> str:
    """Форматирование цены"""
    if p is None:
        return "—"
    if p >= 1000:
        return f"{p:,.2f}".replace(",", " ")
    if p >= 1:
        return f"{p:.2f}"
    if p >= 0.01:
        return f"{p:.4f}"
    return f"{p:.8f}".rstrip("0").rstrip(".")


async def fetch_price_coingecko(coin_id: str) -> Optional[float]:
    """Получение цены через CoinGecko API (бесплатный)"""
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get(coin_id, {}).get("usd")
                    if price:
                        logger.debug(f"CoinGecko: {coin_id} = ${price}")
                        return float(price)
    except Exception as e:
        logger.warning(f"CoinGecko failed for {coin_id}: {e}")
    
    return None


async def fetch_price_binance(symbol: str) -> Optional[float]:
    """Получение цены через Binance Public API (бесплатный)"""
    trading_pair = f"{symbol}USDT"
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={trading_pair}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get("price")
                    if price:
                        logger.debug(f"Binance: {symbol} = ${price}")
                        return float(price)
    except Exception as e:
        logger.warning(f"Binance failed for {symbol}: {e}")
    
    return None


async def get_coin_id_by_symbol(deps: Deps, symbol: str) -> Optional[str]:
    """Получает coin_id по символу"""
    # Сначала проверяем встроенную карту
    coin_id = COIN_MAP.get(symbol.upper())
    if coin_id:
        return coin_id
    
    # Пытаемся через CoinListService
    try:
        coin_list_service = getattr(deps, "coin_list_service", None)
        if coin_list_service and hasattr(coin_list_service, "get_coin_id_by_symbol"):
            coin_id = await coin_list_service.get_coin_id_by_symbol(symbol.upper())
            logger.debug(f"Resolved {symbol} -> {coin_id}")
            return coin_id
    except Exception as e:
        logger.warning(f"Failed to get coin_id for {symbol}: {e}")
    
    return None


async def get_symbol_by_coin_id(deps: Deps, coin_id: str) -> Optional[str]:
    """Получает символ по coin_id"""
    # Проверяем встроенную карту
    for symbol, cid in COIN_MAP.items():
        if cid == coin_id:
            return symbol
    
    # Пытаемся через CoinListService
    try:
        coin_list_service = getattr(deps, "coin_list_service", None)
        if coin_list_service and hasattr(coin_list_service, "get_symbol_by_coin_id"):
            symbol = await coin_list_service.get_symbol_by_coin_id(coin_id)
            return symbol
    except Exception as e:
        logger.warning(f"Failed to get symbol for {coin_id}: {e}")
    
    return None


async def get_price_cached(deps: Deps, symbol: str, coin_id: str) -> Optional[float]:
    """Получает цену с кэшированием и fallback на бесплатные API"""
    now = datetime.now()

    # Проверяем кэш
    cache_key = f"{symbol}:{coin_id}"
    if cache_key in _price_cache:
        cached_price, cached_time = _price_cache[cache_key]
        if now - cached_time < _CACHE_TTL:
            logger.debug(f"Cache hit for {cache_key}: {cached_price}")
            return cached_price

    price = None

    # Пытаемся через price_service
    try:
        price_service = getattr(deps, "price_service", None)
        if price_service and hasattr(price_service, "get_price"):
            await asyncio.sleep(0.1)
            price = await price_service.get_price(coin_id)
            if price is not None:
                price = float(price)
                logger.debug(f"PriceService: {coin_id} = ${price}")
    except Exception as e:
        logger.warning(f"PriceService failed for {coin_id}: {e}")

    # Fallback #1: CoinGecko
    if price is None and coin_id:
        price = await fetch_price_coingecko(coin_id)

    # Fallback #2: Binance
    if price is None and symbol:
        price = await fetch_price_binance(symbol)

    # Кэшируем результат
    if price is not None:
        _price_cache[cache_key] = (price, now)
        logger.debug(f"Fetched and cached price for {cache_key}: {price}")

    return price


def get_price_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с топовыми криптовалютами"""
    buttons = []
    row = []

    for i, symbol in enumerate(DEFAULT_SYMBOLS, 1):
        row.append(
            InlineKeyboardButton(
                text=symbol,
                callback_data=PriceCallback(action="show", coin_id=symbol).pack(),
            )
        )
        if i % 3 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=PriceCallback(action="refresh", coin_id="all").pack(),
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("price"))
async def cmd_price(message: Message, deps: Deps) -> None:
    """Обработчик команды /price"""
    try:
        text = "💰 <b>Цены криптовалют</b>\n\nВыберите монету для просмотра цены:"
        await message.answer(text, parse_mode="HTML", reply_markup=get_price_keyboard())
        logger.info(f"User {message.from_user.id} opened price menu via /price")
    except Exception as e:
        logger.error(f"Error in cmd_price: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.callback_query(PriceCallback.filter(F.action == "open"))
async def price_menu_handler(call: CallbackQuery, deps: Deps) -> None:
    """Обработчик открытия меню цен"""
    try:
        await call.answer()

        text = "💰 <b>Цены криптовалют</b>\n\nВыберите монету для просмотра цены:"

        try:
            await call.message.edit_text(
                text, parse_mode="HTML", reply_markup=get_price_keyboard()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

        logger.info(f"User {call.from_user.id} opened price menu")

    except Exception as e:
        logger.error(f"Error in price_menu_handler: {e}", exc_info=True)
        try:
            await call.answer("⚠️ Произошла ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(PriceCallback.filter(F.action == "show"))
async def price_show_handler(
    call: CallbackQuery, deps: Deps, callback_data: PriceCallback
) -> None:
    """Показывает цену конкретной монеты"""
    try:
        await call.answer("⏳ Загрузка...")

        input_value = callback_data.coin_id
        if not input_value:
            await call.answer("⚠️ Не указана монета", show_alert=True)
            return

        # Преобразуем в symbol и coin_id
        symbol = input_value.upper()
        coin_id = await get_coin_id_by_symbol(deps, symbol)

        if not coin_id:
            coin_id = input_value.lower()
            resolved_symbol = await get_symbol_by_coin_id(deps, coin_id)
            if resolved_symbol:
                symbol = resolved_symbol.upper()

        logger.info(f"Requesting price for symbol={symbol}, coin_id={coin_id}")

        # Получаем цену с fallback на бесплатные API
        price = await get_price_cached(deps, symbol, coin_id)

        if price is None:
            text = (
                f"⚠️ <b>Не удалось получить цену {symbol}</b>\n\n"
                f"Возможные причины:\n"
                f"• Превышен лимит запросов к API\n"
                f"• Монета не найдена\n"
                f"• Временные проблемы с сервисом\n\n"
                f"Попробуйте через минуту."
            )
        else:
            text = (
                f"💰 <b>{symbol}/USD</b>\n\n"
                f"<code>${_fmt_price(price)}</code>\n\n"
                f"<i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"
            )

        try:
            await call.message.edit_text(
                text, parse_mode="HTML", reply_markup=get_price_keyboard()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

        logger.info(f"User {call.from_user.id} viewed price for {symbol}")

    except Exception as e:
        logger.error(f"Error in price_show_handler: {e}", exc_info=True)
        try:
            await call.answer("⚠️ Произошла ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(PriceCallback.filter(F.action == "refresh"))
async def price_refresh_handler(call: CallbackQuery, deps: Deps) -> None:
    """Обновляет меню цен"""
    try:
        _price_cache.clear()
        await call.answer("🔄 Кэш очищен")
        await price_menu_handler(call, deps)
    except Exception as e:
        logger.error(f"Error in price_refresh_handler: {e}", exc_info=True)
        await call.answer("⚠️ Ошибка обновления", show_alert=True)