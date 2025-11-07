# bot/handlers/public/commands/premium.py
"""
Премиум команды: подписка и донаты.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from loguru import logger

router = Router(name="premium_commands_router")


@router.message(Command("premium"))
async def handle_premium(message: Message):
    """Обработчик команды /premium - премиум подписка."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить Premium", callback_data="premium_buy")],
        [
            InlineKeyboardButton(text="📅 1 месяц", callback_data="premium_1m"),
            InlineKeyboardButton(text="📅 3 месяца", callback_data="premium_3m")
        ],
        [
            InlineKeyboardButton(text="📅 6 месяцев", callback_data="premium_6m"),
            InlineKeyboardButton(text="📅 1 год", callback_data="premium_1y")
        ],
        [InlineKeyboardButton(text="🎁 Подарить другу", callback_data="premium_gift")]
    ])
    
    premium_text = (
        f"<b>💎 Mining AI Bot Premium</b>\n\n"
        f"<b>🚀 ПРЕИМУЩЕСТВА ПРЕМИУМ:</b>\n\n"
        
        "⚡ <b>Ускоренный майнинг</b>\n"
        "▪️ x2 скорость добычи\n"
        "▪️ x1.5 к хешрейту\n"
        "▪️ Автоматический майнинг 24/7\n\n"
        
        "🎮 <b>Эксклюзивные возможности</b>\n"
        "▪️ 10 премиум ASIC-ов\n"
        "▪️ Уникальные достижения\n"
        "▪️ Ранний доступ к новинкам\n"
        "▪️ Персональный значок 💎\n\n"
        
        "💰 <b>Финансовые бонусы</b>\n"
        "▪️ +20% к реферальным\n"
        "▪️ Сниженная комиссия вывода\n"
        "▪️ Бесплатные переводы\n"
        "▪️ Приоритет в конкурсах\n\n"
        
        "🆘 <b>VIP поддержка</b>\n"
        "▪️ Приоритетная очередь\n"
        "▪️ Личный менеджер\n"
        "▪️ Помощь 24/7\n\n"
        
        f"<b>💵 ЦЕНЫ:</b>\n"
        "📅 1 месяц → 299₽ (10₽/день)\n"
        "📅 3 месяца → 699₽ (8₽/день) -20%\n"
        "📅 6 месяцев → 1,199₽ (7₽/день) -30%\n"
        "📅 1 год → 1,999₽ (5₽/день) -45%\n\n"
        
        f"<b>🎁 СПЕЦИАЛЬНОЕ ПРЕДЛОЖЕНИЕ:</b>\n"
        "Первая неделя БЕСПЛАТНО!\n"
        "Попробуйте без риска 🎉\n\n"
        
        f"<b>💳 СПОСОБЫ ОПЛАТЫ:</b>\n"
        "▪️ Банковская карта (РФ)\n"
        "▪️ Криптовалюта (BTC, ETH, USDT)\n"
        "▪️ ЮMoney, Qiwi\n"
        "▪️ Telegram Stars\n\n"
        
        "Активируйте Premium и увеличьте доход! 💎"
    )
    
    await message.answer(premium_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened premium")


@router.message(Command("donate"))
async def handle_donate(message: Message):
    """Обработчик команды /donate - поддержка проекта."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Карта (РФ)", callback_data="donate_card")],
        [InlineKeyboardButton(text="₿ Bitcoin", callback_data="donate_btc")],
        [InlineKeyboardButton(text="Ξ Ethereum", callback_data="donate_eth")],
        [InlineKeyboardButton(text="💎 USDT (TRC20)", callback_data="donate_usdt")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="donate_stars")],
        [InlineKeyboardButton(text="🏆 Таблица доноров", callback_data="donate_leaderboard")]
    ])
    
    donate_text = (
        f"<b>❤️ Поддержите Mining AI Bot</b>\n\n"
        
        "🙏 <b>Спасибо за вашу поддержку!</b>\n\n"
        "Ваши донаты помогают нам:\n"
        "▪️ Развивать новый функционал\n"
        "▪️ Улучшать производительность\n"
        "▪️ Проводить конкурсы\n"
        "▪️ Поддерживать серверы\n"
        "▪️ Создавать контент\n\n"
        
        f"<b>🎁 БОНУСЫ ДЛЯ ДОНОРОВ:</b>\n\n"
        
        "💚 100₽+ → Значок донора 🎖️\n"
        "💙 500₽+ → +1000 хешрейта\n"
        "💜 1,000₽+ → Premium на месяц\n"
        "❤️ 5,000₽+ → Premium на год + эксклюзивный ASIC\n"
        "🧡 10,000₽+ → Ваше имя в зале славы\n\n"
        
        f"<b>💳 СПОСОБЫ ДОНАТА:</b>\n\n"
        
        "💳 <b>Банковская карта (РФ)</b>\n"
        f"Сбербанк: <code>2202 2006 1234 5678</code>\n\n"
        
        "₿ <b>Bitcoin</b>\n"
        f"<code>bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh</code>\n\n"
        
        "Ξ <b>Ethereum</b>\n"
        f"<code>0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb</code>\n\n"
        
        "💎 <b>USDT (TRC20)</b>\n"
        f"<code>TYx7x1x1x1x1x1x1x1x1x1x1x1x1x1x</code>\n\n"
        
        f"<b>🏆 ТОП-3 ДОНОРА:</b>\n"
        "🥇 CryptoKing - 50,000₽\n"
        "🥈 BitLord - 35,000₽\n"
        "🥉 HashMaster - 25,000₽\n\n"
        
        f"<b>📊 Собрано за месяц:</b>\n"
        f"Текущий месяц: <code>125,430₽</code> из <code>200,000₽</code>\n"
        "Прогресс: ▓▓▓▓▓▓▓░░░ 62%\n\n"
        
        "Каждый рубль на счету! Спасибо! 🙏❤️"
    )
    
    await message.answer(donate_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened donate")