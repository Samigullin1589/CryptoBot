# bot/handlers/public/commands/start.py
"""
Команды запуска и главного меню.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from loguru import logger

from bot.handlers.public.commands.keyboards import get_main_keyboard

router = Router(name="start_commands_router")


@router.message(Command("start"))
async def handle_start(message: Message):
    """Обработчик команды /start - приветствие и главное меню."""
    user = message.from_user
    
    keyboard = get_main_keyboard()
    
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Начать игру", callback_data="quick_game"),
            InlineKeyboardButton(text="📈 Цены", callback_data="quick_prices")
        ],
        [
            InlineKeyboardButton(text="📋 Все команды", callback_data="show_commands"),
            InlineKeyboardButton(text="❓ Справка", callback_data="show_help")
        ]
    ])
    
    start_text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"🤖 Добро пожаловать в <b>Mining AI Bot</b> — твой персональный помощник в мире криптовалют и майнинга!\n\n"
        
        f"<b>🎯 Что я умею:</b>\n"
        f"⛏ <b>Майнинг-игра</b> — зарабатывай виртуальную криптовалюту\n"
        f"💰 <b>Цены</b> — актуальные курсы криптовалют\n"
        f"📊 <b>Аналитика</b> — графики и рыночные данные\n"
        f"🧠 <b>Обучение</b> — квизы и гайды по крипте\n"
        f"🏆 <b>Достижения</b> — выполняй задачи, получай награды\n"
        f"👥 <b>Рефералы</b> — приглашай друзей и зарабатывай\n\n"
        
        f"<b>💡 Быстрый старт:</b>\n"
        f"1️⃣ Нажми на кнопку ниже или выбери действие из меню\n"
        f"2️⃣ Используй команды для управления ботом\n"
        f"3️⃣ Изучай крипто-мир и зарабатывай!\n\n"
        
        f"📋 <b>Основные команды:</b>\n"
        f"/game — Начать майнинг-игру 🎮\n"
        f"/price — Узнать цены криптовалют 💰\n"
        f"/quiz — Пройти крипто-квиз 🧠\n"
        f"/help — Полная справка ℹ️\n"
        f"/commands — Все команды 📋\n\n"
        
        f"✨ <b>Готов начать?</b> Выбери действие! ⬇️"
    )
    
    await message.answer(start_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await message.answer("🚀 Или используй быстрые кнопки:", reply_markup=inline_keyboard)
    
    logger.info(f"User {user.id} (@{user.username}) started the bot")


@router.message(Command("menu"))
async def handle_menu(message: Message):
    """Обработчик команды /menu - показать главное меню."""
    keyboard = get_main_keyboard()
    
    menu_text = (
        f"<b>📱 Главное меню</b>\n\n"
        f"Выбери раздел, который тебя интересует:\n\n"
        f"💰 <b>Цены</b> — актуальные курсы криптовалют\n"
        f"⛏ <b>Майнинг</b> — майнинг-симулятор\n"
        f"📊 <b>Рынок</b> — рыночная информация\n"
        f"🎮 <b>Игра</b> — игровой режим\n"
        f"🧠 <b>Квиз</b> — тестирование знаний\n"
        f"🏆 <b>Достижения</b> — твои награды\n"
        f"👥 <b>Рефералы</b> — пригласи друзей\n"
        f"💎 <b>Премиум</b> — премиум подписка\n"
        f"ℹ️ <b>Помощь</b> — справочная информация\n"
        f"⚙️ <b>Настройки</b> — настрой бота\n\n"
        f"Также доступны команды:\n"
        f"/commands — полный список команд\n"
        f"/help — подробная справка"
    )
    
    await message.answer(menu_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened menu")


@router.message(Command("help"))
async def handle_help(message: Message):
    """Обработчик команды /help - подробная справка."""
    help_text = (
        f"<b>📚 Справка по боту</b>\n\n"
        
        f"<b>🎮 ОСНОВНЫЕ РАЗДЕЛЫ:</b>\n\n"
        
        f"⛏ <b>МАЙНИНГ</b>\n"
        f"/game — Запустить майнинг-игру\n"
        f"/achievements — Твои достижения\n"
        f"/leaderboard — Таблица лидеров\n"
        f"/profile — Твой профиль\n\n"
        
        f"💰 <b>РЫНОК И ЦЕНЫ</b>\n"
        f"/price [монета] — Узнать цену криптовалюты\n"
        f"/news — Последние крипто-новости\n"
        f"/chart [монета] — График цены\n"
        f"/calculator — Калькулятор доходности\n\n"
        
        f"🧠 <b>ОБУЧЕНИЕ</b>\n"
        f"/quiz — Крипто-квиз\n"
        f"/learn — Образовательные материалы\n"
        f"/faq — Частые вопросы\n\n"
        
        f"👥 <b>СОЦИАЛЬНОЕ</b>\n"
        f"/invite — Пригласить друга (бонусы!)\n"
        f"/community — Наше сообщество\n"
        f"/events — Актуальные события\n\n"
        
        f"💎 <b>ПРЕМИУМ</b>\n"
        f"/premium — Премиум подписка\n"
        f"/donate — Поддержать проект\n\n"
        
        f"⚙️ <b>НАСТРОЙКИ</b>\n"
        f"/settings — Настройки бота\n"
        f"/feedback — Оставить отзыв\n"
        f"/support — Техподдержка\n\n"
        
        f"ℹ️ <b>ИНФОРМАЦИЯ</b>\n"
        f"/about — О боте\n"
        f"/commands — Все команды\n"
        f"/version — Версия бота\n"
        f"/status — Статус систем\n\n"
        
        f"<b>💡 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:</b>\n"
        f"• <code>/price btc</code> — цена Bitcoin\n"
        f"• <code>/game</code> — начать майнить\n"
        f"• <code>/quiz</code> — пройти тест\n"
        f"• <code>/invite</code> — пригласить друга\n\n"
        
        f"❓ Остались вопросы? Напиши /support"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /help")


@router.callback_query(F.data == "quick_game")
async def handle_quick_game(callback):
    """Быстрый доступ к игре"""
    await callback.answer("🎮 Запускаем игру...")
    await callback.message.answer(
        "🎮 Майнинг-игра запускается!\n\nИспользуй /game для полного функционала"
    )


@router.callback_query(F.data == "quick_prices")
async def handle_quick_prices(callback):
    """Быстрый доступ к ценам"""
    await callback.answer("💰 Загружаем цены...")
    await callback.message.answer(
        "💰 Актуальные цены криптовалют\n\nИспользуй /price [монета] для подробной информации"
    )


@router.callback_query(F.data == "show_commands")
async def handle_show_commands(callback):
    """Показать все команды"""
    from bot.handlers.public.commands.info import handle_commands
    await callback.message.delete()
    await handle_commands(callback.message)
    await callback.answer()


@router.callback_query(F.data == "show_help")
async def handle_show_help(callback):
    """Показать справку"""
    await callback.message.delete()
    await handle_help(callback.message)
    await callback.answer()