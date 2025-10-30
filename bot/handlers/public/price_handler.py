# src/bot/handlers/public/price_handler.py
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from bot.keyboards.callback_factories import PriceCallback
from bot.utils.dependencies import Deps

router = Router(name="price_public")

# Кэш цен с timestamp
_price_cache: Dict[str, tuple[float, datetime]] = {}
_CACHE_TTL = timedelta(seconds=60)  # 60 секунд кэш

# Популярные монеты по умолчанию
DEFAULT_SYMBOLS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "TRX", "MATIC", "LTC", "AVAX"]


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
        
        # Добавляем небольшую задержку между запросами
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
    """Клавиатура с топовыми криптовалютами"""
    buttons = []
    row = []
    
    for i, symbol in enumerate(DEFAULT_SYMBOLS, 1):
        row.append(InlineKeyboardButton(
            text=symbol,
            callback_data=PriceCallback(action="show", coin_id=symbol.lower()).pack()
        ))
        if i % 3 == 0:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([
        InlineKeyboardButton(
            text="🔍 Найти монету",
            callback_data=PriceCallback(action="search", coin_id="").pack()
        ),
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=PriceCallback(action="refresh", coin_id="all").pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=PriceCallback(action="open", coin_id="").pack()
        )]
    ])


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
    """Обработчик открытия меню цен из главного меню"""
    try:
        await call.answer()
        
        text = "💰 <b>Цены криптовалют</b>\n\nВыберите монету для просмотра цены:"
        
        await call.message.edit_text(
            text, 
            parse_mode="HTML", 
            reply_markup=get_price_keyboard()
        )
        
        logger.info(f"User {call.from_user.id} opened price menu")
        
    except Exception as e:
        logger.error(f"Error in price_menu_handler: {e}", exc_info=True)
        
        try:
            await call.answer("⚠️ Произошла ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(PriceCallback.filter(F.action == "show"))
async def price_show_handler(call: CallbackQuery, deps: Deps, callback_data: PriceCallback) -> None:
    """Показывает цену конкретной монеты"""
    try:
        await call.answer("⏳ Загрузка...")
        
        coin_id = callback_data.coin_id
        if not coin_id:
            await call.answer("⚠️ Не указана монета", show_alert=True)
            return
        
        # Если передан символ, получаем coin_id
        if coin_id.upper() in DEFAULT_SYMBOLS:
            resolved_coin_id = await get_coin_id_by_symbol(deps, coin_id.upper())
            if not resolved_coin_id:
                # Fallback на простое преобразование
                resolved_coin_id = coin_id.lower()
            symbol = coin_id.upper()
        else:
            resolved_coin_id = coin_id
            symbol = await get_symbol_by_coin_id(deps, coin_id)
            if not symbol:
                symbol = coin_id.upper()
        
        # Получаем цену с кэшированием
        price = await get_price_cached(deps, resolved_coin_id)
        
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
        
        await call.message.edit_text(
            text, 
            parse_mode="HTML", 
            reply_markup=get_price_keyboard()
        )
        
        logger.info(f"User {call.from_user.id} viewed price for {symbol}")
        
    except Exception as e:
        logger.error(f"Error in price_show_handler: {e}", exc_info=True)
        
        try:
            await call.answer("⚠️ Произошла ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(PriceCallback.filter(F.action == "search"))
async def price_search_handler(call: CallbackQuery, deps: Deps) -> None:
    """Обработчик поиска монет"""
    try:
        await call.answer()
        
        text = (
            "🔍 <b>Поиск монеты</b>\n\n"
            "Отправьте символ или название монеты:\n"
            "Например: <code>BTC</code>, <code>ETH</code>, <code>LINK</code>\n\n"
            "Для отмены нажмите кнопку ниже."
        )
        
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        
        logger.info(f"User {call.from_user.id} initiated coin search")
        
    except Exception as e:
        logger.error(f"Error in price_search_handler: {e}", exc_info=True)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_coin_search(message: Message, deps: Deps) -> None:
    """Обрабатывает поиск монеты по тексту"""
    try:
        search_text = message.text.strip().upper()
        
        if len(search_text) < 2 or len(search_text) > 10:
            await message.answer(
                "⚠️ Введите корректный символ монеты (2-10 символов)\n"
                "Например: BTC, ETH, LINK"
            )
            return
        
        # Ищем coin_id по символу
        coin_id = await get_coin_id_by_symbol(deps, search_text)
        
        if not coin_id:
            await message.answer(
                f"❌ Монета <b>{search_text}</b> не найдена\n\n"
                f"Проверьте правильность символа",
                parse_mode="HTML",
                reply_markup=get_price_keyboard()
            )
            return
        
        # Получаем цену
        price = await get_price_cached(deps, coin_id)
        
        if price is None:
            text = (
                f"⚠️ <b>Не удалось получить цену {search_text}</b>\n\n"
                f"Попробуйте позже."
            )
        else:
            text = (
                f"💰 <b>{search_text}/USD</b>\n\n"
                f"<code>${_fmt_price(price)}</code>\n\n"
                f"<i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"
            )
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_price_keyboard()
        )
        
        logger.info(f"User {message.from_user.id} searched and viewed price for {search_text}")
        
    except Exception as e:
        logger.error(f"Error in handle_coin_search: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка при поиске")


@router.callback_query(PriceCallback.filter(F.action == "refresh"))
async def price_refresh_handler(call: CallbackQuery, deps: Deps) -> None:
    """Обновляет меню цен"""
    try:
        # Очищаем кэш
        _price_cache.clear()
        
        await call.answer("🔄 Кэш очищен")
        await price_menu_handler(call, deps)
        
    except Exception as e:
        logger.error(f"Error in price_refresh_handler: {e}", exc_info=True)
        await call.answer("⚠️ Ошибка обновления", show_alert=True)