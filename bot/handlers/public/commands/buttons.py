# bot/handlers/public/commands/buttons.py
"""
Обработчики текстовых кнопок меню.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode

router = Router(name="buttons_router")


@router.message(F.text == "💰 Цены")
async def handle_prices_button(message: Message):
    """Обработчик кнопки Цены"""
    text = (
        "💰 <b>Раздел цен криптовалют</b>\n\n"
        "Используй /price [монета] для получения актуальной цены\n\n"
        "<b>Примеры:</b>\n"
        "• /price btc\n"
        "• /price eth\n"
        "• /price sol"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "⛏ Майнинг")
async def handle_mining_button(message: Message):
    """Обработчик кнопки Майнинг"""
    text = (
        "⛏ <b>Майнинг-симулятор</b>\n\n"
        "Используй /game для запуска игры"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "📊 Рынок")
async def handle_market_button(message: Message):
    """Обработчик кнопки Рынок"""
    text = (
        "📊 <b>Рыночная информация</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "• /price — цены\n"
        "• /news — новости\n"
        "• /chart — графики"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "🎮 Игра")
async def handle_game_button(message: Message):
    """Обработчик кнопки Игра"""
    text = (
        "🎮 <b>Игровой раздел</b>\n\n"
        "<b>Команды:</b>\n"
        "• /game — майнинг-игра\n"
        "• /achievements — достижения\n"
        "• /leaderboard — рейтинг"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "🧠 Квиз")
async def handle_quiz_button(message: Message):
    """Обработчик кнопки Квиз"""
    text = (
        "🧠 <b>Крипто-квиз</b>\n\n"
        "Используй /quiz для начала тестирования"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "🏆 Достижения")
async def handle_achievements_button(message: Message):
    """Обработчик кнопки Достижения"""
    text = (
        "🏆 <b>Твои достижения</b>\n\n"
        "Используй /achievements для просмотра"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "👥 Рефералы")
async def handle_referrals_button(message: Message):
    """Обработчик кнопки Рефералы"""
    text = (
        "👥 <b>Реферальная программа</b>\n\n"
        "Используй /invite для приглашения друзей"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "💎 Премиум")
async def handle_premium_button(message: Message):
    """Обработчик кнопки Премиум"""
    text = (
        "💎 <b>Премиум подписка</b>\n\n"
        "Используй /premium для подробностей"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "ℹ️ Помощь")
async def handle_help_button(message: Message):
    """Обработчик кнопки Помощь"""
    from bot.handlers.public.commands.start import handle_help
    await handle_help(message)


@router.message(F.text == "⚙️ Настройки")
async def handle_settings_button(message: Message):
    """Обработчик кнопки Настройки"""
    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        "Используй /settings для управления настройками"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)