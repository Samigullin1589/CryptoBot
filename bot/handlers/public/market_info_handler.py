# bot/handlers/public/market_info_handler.py

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.services.market_data_service import MarketDataService
from bot.keyboards.inline.market_keyboards import get_market_menu_keyboard

router = Router(name="market_info_handler")


@router.callback_query(F.data == "market_info")
async def market_info_menu(
    callback: CallbackQuery,
    market_data_service: MarketDataService
):
    """Главное меню рыночной информации"""
    try:
        await callback.answer()
        
        text = (
            "📊 <b>Рыночная информация</b>\n\n"
            "Выберите раздел для получения актуальной информации о криптовалютном рынке:"
        )
        
        keyboard = get_market_menu_keyboard()
        
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
                
    except Exception as e:
        logger.error(f"Ошибка в market_info_menu: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "btc_network_status")
async def handle_btc_status(
    callback: CallbackQuery,
    market_data_service: MarketDataService
):
    """Обработчик статуса сети Bitcoin"""
    try:
        await callback.answer("Получаю данные о сети Bitcoin...")
        
        # Получаем данные о сети
        status = await market_data_service.get_btc_network_status()
        
        if not status:
            # Вместо raise используем graceful fallback
            text = (
                "⚠️ <b>Статус сети Bitcoin</b>\n\n"
                "К сожалению, не удалось получить актуальные данные о сети Bitcoin.\n"
                "Попробуйте позже или выберите другой раздел."
            )
        else:
            # Форматируем данные
            difficulty = status.get("difficulty", 0)
            hash_rate = status.get("hash_rate", 0)
            blocks = status.get("blocks_count", 0)
            next_retarget = status.get("next_retarget", 0)
            
            # Конвертируем hash rate в читаемый формат
            if hash_rate > 0:
                hash_rate_eh = hash_rate / 1_000_000_000_000_000_000  # в EH/s
                hash_rate_str = f"{hash_rate_eh:.2f} EH/s"
            else:
                hash_rate_str = "Н/Д"
            
            text = (
                f"⛏ <b>Статус сети Bitcoin</b>\n\n"
                f"📊 <b>Сложность:</b> {difficulty:,.0f}\n"
                f"⚡️ <b>Хешрейт:</b> {hash_rate_str}\n"
                f"📦 <b>Блоков:</b> {blocks:,}\n"
                f"🎯 <b>След. корректировка:</b> блок {next_retarget:,}\n\n"
                f"<i>Данные обновляются в реальном времени</i>"
            )
        
        keyboard = get_market_menu_keyboard()
        
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
                
        logger.info(f"User {callback.from_user.id} viewed BTC network status")
        
    except Exception as e:
        logger.error(f"Ошибка в handle_btc_status: {e}")
        try:
            await callback.message.edit_text(
                text=(
                    "❌ <b>Ошибка</b>\n\n"
                    "Не удалось загрузить данные о сети Bitcoin.\n"
                    "Попробуйте позже."
                ),
                reply_markup=get_market_menu_keyboard(),
                parse_mode="HTML"
            )
        except:
            await callback.answer(
                "Произошла ошибка при загрузке данных.",
                show_alert=True
            )


@router.callback_query(F.data == "market_overview")
async def handle_market_overview(
    callback: CallbackQuery,
    market_data_service: MarketDataService
):
    """Общий обзор рынка"""
    try:
        await callback.answer("Загружаю обзор рынка...")
        
        # Получаем топ монет
        top_coins = ["btc", "eth", "bnb", "xrp", "ada", "sol", "doge", "dot"]
        prices = await market_data_service.get_prices(top_coins)
        
        text = "📈 <b>Обзор криптовалютного рынка</b>\n\n"
        
        coin_names = {
            "btc": "Bitcoin",
            "eth": "Ethereum", 
            "bnb": "BNB",
            "xrp": "XRP",
            "ada": "Cardano",
            "sol": "Solana",
            "doge": "Dogecoin",
            "dot": "Polkadot"
        }
        
        for coin_id, price in prices.items():
            if price:
                name = coin_names.get(coin_id, coin_id.upper())
                text += f"• <b>{name}:</b> ${price:,.2f}\n"
        
        text += "\n<i>Данные обновляются каждые 30 секунд</i>"
        
        keyboard = get_market_menu_keyboard()
        
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
                
        logger.info(f"User {callback.from_user.id} viewed market overview")
        
    except Exception as e:
        logger.error(f"Ошибка в handle_market_overview: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("market_"))
async def handle_market_back(callback: CallbackQuery):
    """Обработчик возврата в меню"""
    if callback.data == "market_back":
        await market_info_menu(callback, callback.bot.get("market_data_service"))