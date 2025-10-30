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

from bot.keyboards.callback_factories import PriceCallback
from bot.utils.dependencies import Deps

router = Router(name="price_public")

# Кэш цен с timestamp
_price_cache: Dict[str, tuple[float, datetime]] = {}
_CACHE_TTL = timedelta(seconds=60)

# Популярные монеты (СИМВОЛЫ)
DEFAULT_SYMBOLS = [
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "XRP",
    "ADA",
    "DOGE",
    "DOT",
    "TRX",
    "MATIC",
    "LTC",
    "AVAX",
]


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


async def get_coin_id_by_symbol(deps: Deps, symbol: str) -> Optional[str]:
    """Получает coin_id по символу через CoinListService"""
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
    """Получает символ по coin_id через CoinListService"""
    try:
        coin_list_service = getattr(deps, "coin_list_service", None)
        if coin_list_service and hasattr(coin_list_service, "get_symbol_by_coin_id"):
            symbol = await coin_list_service.get_symbol_by_coin_id(coin_id)
            return symbol
    except Exception as e:
        logger.warning(f"Failed to get symbol for {coin_id}: {e}")
    return None


async def get_price_cached(deps: Deps, coin_id: str) -> Optional[float]:
    """Получает цену с кэшированием"""
    now = datetime.now()

    # Проверяем кэш
    if coin_id in _price_cache:
        cached_price, cached_time = _price_cache[coin_id]
        if now - cached_time < _CACHE_TTL:
            logger.debug(f"Cache hit for {coin_id}: {cached_price}")
            return cached_price

    # Запрашиваем свежую цену
    try:
        price_service = getattr(deps, "price_service", None)
        if not price_service or not hasattr(price_service, "get_price"):
            logger.warning("price_service not available")
            return None

        await asyncio.sleep(0.1)

        price = await price_service.get_price(coin_id)
        if price is not None:
            price = float(price)
            _price_cache[coin_id] = (price, now)
            logger.debug(f"Fetched and cached price for {coin_id}: {price}")
            return price

    except Exception as e:
        logger.error(f"Error getting price for {coin_id}: {e}")

    return None


def get_price_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с топовыми криптовалютами - передаем СИМВОЛЫ"""
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

        # ВСЕГДА пытаемся преобразовать в coin_id через CoinListService
        symbol = input_value.upper()
        coin_id = await get_coin_id_by_symbol(deps, symbol)

        if not coin_id:
            # Если не нашли через CoinListService, возможно это уже coin_id
            coin_id = input_value.lower()
            # Пытаемся получить символ обратно
            resolved_symbol = await get_symbol_by_coin_id(deps, coin_id)
            if resolved_symbol:
                symbol = resolved_symbol.upper()
            else:
                symbol = input_value.upper()

        logger.info(f"Requesting price for symbol={symbol}, coin_id={coin_id}")

        # Получаем цену с кэшированием
        price = await get_price_cached(deps, coin_id)

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