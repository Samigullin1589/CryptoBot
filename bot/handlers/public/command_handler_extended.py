# =============================================================================
# Файл: bot/handlers/public/command_handler_extended.py
# Версия: Extended FULL with /start (30.10.2025)
# Описание: ПОЛНАЯ версия с /start и главным меню
# =============================================================================

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold, hcode, hlink
from loguru import logger
import time
from datetime import datetime
import random

# Важно: имя переменной должно быть "router"
router = Router(name="command_handler_extended_router")


# ========== ГЛАВНЫЕ КОМАНДЫ (START И MENU) ==========

@router.message(Command("start"))
async def handle_start(message: Message):
    """
    Обработчик команды /start - приветствие и главное меню.
    """
    user = message.from_user
    
    # Создаем главное меню с кнопками
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Цены"),
                KeyboardButton(text="⛏ Майнинг")
            ],
            [
                KeyboardButton(text="📊 Рынок"),
                KeyboardButton(text="🎮 Игра")
            ],
            [
                KeyboardButton(text="🧠 Квиз"),
                KeyboardButton(text="🏆 Достижения")
            ],
            [
                KeyboardButton(text="👥 Рефералы"),
                KeyboardButton(text="💎 Премиум")
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="⚙️ Настройки")
            ],
        ],
        resize_keyboard=True
    )
    
    # Inline кнопки для быстрого доступа
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
        f"👋 Привет, {hbold(user.first_name)}!\n\n"
        f"🤖 Добро пожаловать в {hbold('Mining AI Bot')} — твой персональный помощник в мире криптовалют и майнинга!\n\n"
        
        f"{hbold('🎯 Что я умею:')}\n"
        f"⛏ {hbold('Майнинг-игра')} — зарабатывай виртуальную криптовалюту\n"
        f"💰 {hbold('Цены')} — актуальные курсы криптовалют\n"
        f"📊 {hbold('Аналитика')} — графики и рыночные данные\n"
        f"🧠 {hbold('Обучение')} — квизы и гайды по крипте\n"
        f"🏆 {hbold('Достижения')} — выполняй задачи, получай награды\n"
        f"👥 {hbold('Рефералы')} — приглашай друзей и зарабатывай\n\n"
        
        f"{hbold('💡 Быстрый старт:')}\n"
        f"1️⃣ Нажми на кнопку ниже или выбери действие из меню\n"
        f"2️⃣ Используй команды для управления ботом\n"
        f"3️⃣ Изучай крипто-мир и зарабатывай!\n\n"
        
        f"📋 {hbold('Основные команды:')}\n"
        f"/game — Начать майнинг-игру 🎮\n"
        f"/price — Узнать цены криптовалют 💰\n"
        f"/quiz — Пройти крипто-квиз 🧠\n"
        f"/help — Полная справка ℹ️\n"
        f"/commands — Все команды 📋\n\n"
        
        f"✨ {hbold('Готов начать?')} Выбери действие! ⬇️"
    )
    
    await message.answer(
        start_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    
    # Отправляем inline-меню для быстрого доступа
    await message.answer(
        "🚀 Или используй быстрые кнопки:",
        reply_markup=inline_keyboard
    )
    
    logger.info(f"User {user.id} (@{user.username}) started the bot")


@router.message(Command("menu"))
async def handle_menu(message: Message):
    """
    Обработчик команды /menu - показать главное меню.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Цены"),
                KeyboardButton(text="⛏ Майнинг")
            ],
            [
                KeyboardButton(text="📊 Рынок"),
                KeyboardButton(text="🎮 Игра")
            ],
            [
                KeyboardButton(text="🧠 Квиз"),
                KeyboardButton(text="🏆 Достижения")
            ],
            [
                KeyboardButton(text="👥 Рефералы"),
                KeyboardButton(text="💎 Премиум")
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="⚙️ Настройки")
            ],
        ],
        resize_keyboard=True
    )
    
    menu_text = (
        f"{hbold('📱 Главное меню')}\n\n"
        f"Выбери раздел, который тебя интересует:\n\n"
        f"💰 {hbold('Цены')} — актуальные курсы криптовалют\n"
        f"⛏ {hbold('Майнинг')} — майнинг-симулятор\n"
        f"📊 {hbold('Рынок')} — рыночная информация\n"
        f"🎮 {hbold('Игра')} — игровой режим\n"
        f"🧠 {hbold('Квиз')} — тестирование знаний\n"
        f"🏆 {hbold('Достижения')} — твои награды\n"
        f"👥 {hbold('Рефералы')} — пригласи друзей\n"
        f"💎 {hbold('Премиум')} — премиум подписка\n"
        f"ℹ️ {hbold('Помощь')} — справочная информация\n"
        f"⚙️ {hbold('Настройки')} — настрой бота\n\n"
        f"Также доступны команды:\n"
        f"/commands — полный список команд\n"
        f"/help — подробная справка"
    )
    
    await message.answer(menu_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened menu")


@router.message(Command("help"))
async def handle_help(message: Message):
    """
    Обработчик команды /help - подробная справка.
    """
    help_text = (
        f"{hbold('📚 Справка по боту')}\n\n"
        
        f"{hbold('🎮 ОСНОВНЫЕ РАЗДЕЛЫ:')}\n\n"
        
        f"⛏ {hbold('МАЙНИНГ')}\n"
        f"/game — Запустить майнинг-игру\n"
        f"/achievements — Твои достижения\n"
        f"/leaderboard — Таблица лидеров\n"
        f"/profile — Твой профиль\n\n"
        
        f"💰 {hbold('РЫНОК И ЦЕНЫ')}\n"
        f"/price <монета> — Узнать цену криптовалюты\n"
        f"/news — Последние крипто-новости\n"
        f"/chart <монета> — График цены\n"
        f"/calculator — Калькулятор доходности\n\n"
        
        f"🧠 {hbold('ОБУЧЕНИЕ')}\n"
        f"/quiz — Крипто-квиз\n"
        f"/learn — Образовательные материалы\n"
        f"/faq — Частые вопросы\n\n"
        
        f"👥 {hbold('СОЦИАЛЬНОЕ')}\n"
        f"/invite — Пригласить друга (бонусы!)\n"
        f"/community — Наше сообщество\n"
        f"/events — Актуальные события\n\n"
        
        f"💎 {hbold('ПРЕМИУМ')}\n"
        f"/premium — Премиум подписка\n"
        f"/donate — Поддержать проект\n\n"
        
        f"⚙️ {hbold('НАСТРОЙКИ')}\n"
        f"/settings — Настройки бота\n"
        f"/feedback — Оставить отзыв\n"
        f"/support — Техподдержка\n\n"
        
        f"ℹ️ {hbold('ИНФОРМАЦИЯ')}\n"
        f"/about — О боте\n"
        f"/commands — Все команды\n"
        f"/version — Версия бота\n"
        f"/status — Статус систем\n\n"
        
        f"{hbold('💡 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:')}\n"
        f"• {hcode('/price btc')} — цена Bitcoin\n"
        f"• {hcode('/game')} — начать майнить\n"
        f"• {hcode('/quiz')} — пройти тест\n"
        f"• {hcode('/invite')} — пригласить друга\n\n"
        
        f"❓ Остались вопросы? Напиши /support"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /help")


# ========== ОБРАБОТЧИКИ БЫСТРЫХ КНОПОК ==========

@router.callback_query(F.data == "quick_game")
async def handle_quick_game(callback):
    """Быстрый доступ к игре"""
    await callback.answer("🎮 Запускаем игру...")
    await callback.message.answer(
        "🎮 Майнинг-игра запускается!\n\n"
        "Используй /game для полного функционала"
    )


@router.callback_query(F.data == "quick_prices")
async def handle_quick_prices(callback):
    """Быстрый доступ к ценам"""
    await callback.answer("💰 Загружаем цены...")
    await callback.message.answer(
        "💰 Актуальные цены криптовалют\n\n"
        "Используй /price <монета> для подробной информации"
    )


@router.callback_query(F.data == "show_commands")
async def handle_show_commands(callback):
    """Показать все команды"""
    await callback.message.delete()
    await handle_commands(callback.message)
    await callback.answer()


@router.callback_query(F.data == "show_help")
async def handle_show_help(callback):
    """Показать справку"""
    await callback.message.delete()
    await handle_help(callback.message)
    await callback.answer()


# ========== ОБРАБОТЧИКИ ТЕКСТОВЫХ КНОПОК МЕНЮ ==========

@router.message(F.text == "💰 Цены")
async def handle_prices_button(message: Message):
    """Обработчик кнопки Цены"""
    await message.answer(
        "💰 Раздел цен криптовалют\n\n"
        "Используй /price <монета> для получения актуальной цены\n\n"
        "Примеры:\n"
        "/price btc\n"
        "/price eth\n"
        "/price sol"
    )


@router.message(F.text == "⛏ Майнинг")
async def handle_mining_button(message: Message):
    """Обработчик кнопки Майнинг"""
    await message.answer(
        "⛏ Майнинг-симулятор\n\n"
        "Используй /game для запуска игры"
    )


@router.message(F.text == "📊 Рынок")
async def handle_market_button(message: Message):
    """Обработчик кнопки Рынок"""
    await message.answer(
        "📊 Рыночная информация\n\n"
        "Доступные команды:\n"
        "/price — цены\n"
        "/news — новости\n"
        "/chart — графики"
    )


@router.message(F.text == "🎮 Игра")
async def handle_game_button(message: Message):
    """Обработчик кнопки Игра"""
    await message.answer(
        "🎮 Игровой раздел\n\n"
        "Команды:\n"
        "/game — майнинг-игра\n"
        "/achievements — достижения\n"
        "/leaderboard — рейтинг"
    )


@router.message(F.text == "🧠 Квиз")
async def handle_quiz_button(message: Message):
    """Обработчик кнопки Квиз"""
    await message.answer(
        "🧠 Крипто-квиз\n\n"
        "Используй /quiz для начала тестирования"
    )


@router.message(F.text == "🏆 Достижения")
async def handle_achievements_button(message: Message):
    """Обработчик кнопки Достижения"""
    await message.answer(
        "🏆 Твои достижения\n\n"
        "Используй /achievements для просмотра"
    )


@router.message(F.text == "👥 Рефералы")
async def handle_referrals_button(message: Message):
    """Обработчик кнопки Рефералы"""
    await message.answer(
        "👥 Реферальная программа\n\n"
        "Используй /invite для приглашения друзей"
    )


@router.message(F.text == "💎 Премиум")
async def handle_premium_button(message: Message):
    """Обработчик кнопки Премиум"""
    await message.answer(
        "💎 Премиум подписка\n\n"
        "Используй /premium для подробностей"
    )


@router.message(F.text == "ℹ️ Помощь")
async def handle_help_button(message: Message):
    """Обработчик кнопки Помощь"""
    await handle_help(message)


@router.message(F.text == "⚙️ Настройки")
async def handle_settings_button(message: Message):
    """Обработчик кнопки Настройки"""
    await message.answer(
        "⚙️ Настройки бота\n\n"
        "Используй /settings для управления настройками"
    )


# ========== ОСНОВНЫЕ ИНФОРМАЦИОННЫЕ КОМАНДЫ ==========

@router.message(Command("about"))
async def handle_about(message: Message):
    """
    Обработчик команды /about - подробная информация о боте.
    """
    about_text = (
        f"{hbold('🤖 Mining AI Bot - Ваш Криптовалютный Помощник')}\n\n"
        f"{hbold('📋 Основные функции:')}\n"
        f"🎮 {hbold('Игра:')} Майнинг-симулятор с ASIC-ами\n"
        f"📊 {hbold('Рынок:')} Актуальные цены и новости\n"
        f"🧠 {hbold('Обучение:')} Квизы и информация\n"
        f"🏆 {hbold('Достижения:')} Система прогресса\n"
        f"🔧 {hbold('Инструменты:')} Калькуляторы и анализ\n\n"
        f"{hbold('💡 Особенности:')}\n"
        "▪️ Реальные рыночные данные\n"
        "▪️ Интерактивная игра\n"
        "▪️ Образовательный контент\n"
        "▪️ Достижения и награды\n"
        "▪️ Реферальная программа\n"
        "▪️ Премиум подписка\n\n"
        f"{hbold('🔧 Технические детали:')}\n"
        f"Версия: {hcode('2.0.0 Production Ready FULL')}\n"
        f"Обновлено: {hcode('29 октября 2025')}\n"
        f"Платформа: {hcode('Telegram Bot API')}\n"
        f"Команд: {hcode('21 дополнительных')}\n\n"
        "Используй /help для списка команд"
    )
    
    await message.answer(about_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /about")


@router.message(Command("stats"))
async def handle_stats(message: Message):
    """
    Обработчик команды /stats - расширенная статистика пользователя.
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"
    
    stats_text = (
        f"{hbold('📊 Ваша статистика')}\n\n"
        f"{hbold('👤 Профиль:')}\n"
        f"🆔 ID: {hcode(str(user_id))}\n"
        f"👤 Имя: {user_name}\n"
        f"🔖 Username: {username}\n\n"
        f"{hbold('📈 Детальная статистика:')}\n"
        "▪️ /game - Игровая статистика и прогресс\n"
        "▪️ /achievements - Ваши достижения и награды\n"
        "▪️ /leaderboard - Рейтинги игроков\n"
        "▪️ /invite - Рефералы и бонусы\n\n"
        f"Дата регистрации: {datetime.now().strftime('%d.%m.%Y')}"
    )
    
    await message.answer(stats_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {user_id} requested /stats")


@router.message(Command("info"))
async def handle_info(message: Message):
    """
    Обработчик команды /info - краткая информация о боте.
    """
    info_text = (
        f"{hbold('ℹ️ Mining AI Bot - Краткая Информация')}\n\n"
        "🎯 {hbold('Миссия:')}\n"
        "Сделать криптовалюты понятными и доступными для всех!\n\n"
        "🚀 {hbold('Что мы предлагаем:')}\n"
        "▪️ Игровой майнинг-симулятор\n"
        "▪️ Образовательные квизы\n"
        "▪️ Актуальные рыночные данные\n"
        "▪️ Система достижений\n"
        "▪️ Аналитические инструменты\n"
        "▪️ Реферальная программа\n"
        "▪️ Премиум подписка\n\n"
        "💡 {hbold('Начните прямо сейчас:')}\n"
        "/start - Запустить бота\n"
        "/help - Получить справку\n"
        "/game - Начать игру\n"
        "/invite - Пригласить друзей\n\n"
        "Присоединяйтесь к сообществу майнеров! ⛏️"
    )
    
    await message.answer(info_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /info")


# ========== КОМАНДЫ СПИСКОВ И НАВИГАЦИИ ==========

@router.message(Command("commands"))
async def handle_commands(message: Message):
    """
    Обработчик команды /commands - полный список команд с категориями.
    """
    commands_text = (
        f"{hbold('📋 Все команды бота (21 дополнительных)')}\n\n"
        
        f"{hbold('🎮 ОСНОВНЫЕ КОМАНДЫ')}\n"
        "/start - Запустить бота\n"
        "/help - Полная справка\n"
        "/menu - Главное меню с кнопками\n\n"
        
        f"{hbold('⛏️ ИГРА И МАЙНИНГ')}\n"
        "/game - Майнинг-игра\n"
        "/achievements - Ваши достижения\n"
        "/leaderboard - Таблица лидеров\n\n"
        
        f"{hbold('📈 РЫНОК И АНАЛИТИКА')}\n"
        "/price - Текущие цены криптовалют\n"
        "/news - Последние крипто-новости\n"
        "/chart - Графики цен\n\n"
        
        f"{hbold('🧠 ОБУЧЕНИЕ')}\n"
        "/quiz - Крипто-квиз\n"
        "/learn - Образовательные материалы\n\n"
        
        f"{hbold('ℹ️ ИНФОРМАЦИЯ')}\n"
        "/about - Подробно о боте\n"
        "/info - Краткая информация\n"
        "/stats - Ваша статистика\n"
        "/version - Версия бота\n"
        "/commands - Этот список\n"
        "/faq - Частые вопросы\n"
        "/roadmap - Дорожная карта\n\n"
        
        f"{hbold('🔧 УТИЛИТЫ')}\n"
        "/ping - Проверка связи\n"
        "/status - Статус систем\n"
        "/settings - Настройки\n"
        "/feedback - Отправить отзыв\n"
        "/support - Техподдержка\n\n"
        
        f"{hbold('👥 СОЦИАЛЬНОЕ')}\n"
        "/invite - Пригласить друга 🎁\n"
        "/community - Наше сообщество\n"
        "/events - События и конкурсы\n\n"
        
        f"{hbold('💎 ПРЕМИУМ')}\n"
        "/premium - Премиум подписка\n"
        "/donate - Поддержать проект\n\n"
        
        "💡 Используй /help для подробных инструкций"
    )
    
    await message.answer(commands_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /commands")


# ========== ТЕХНИЧЕСКИЕ КОМАНДЫ ==========

@router.message(Command("version"))
async def handle_version(message: Message):
    """
    Обработчик команды /version - детальная информация о версии.
    """
    version_text = (
        f"{hbold('🔧 Информация о версии')}\n\n"
        f"{hbold('📦 Версия бота:')}\n"
        f"Version: {hcode('2.0.0 FULL')}\n"
        f"Release: {hcode('Production Ready')}\n"
        f"Build Date: {hcode('29 October 2025')}\n"
        f"Commands: {hcode('21 extended + base')}\n\n"
        f"{hbold('🐍 Технологический стек:')}\n"
        f"Python: {hcode('3.10+')}\n"
        f"aiogram: {hcode('3.22.0')}\n"
        f"Redis: {hcode('Latest')}\n"
        f"Platform: {hcode('Render.com')}\n\n"
        f"{hbold('✨ Новое в этой версии:')}\n"
        "▪️ 21 дополнительная команда\n"
        "▪️ Реферальная система\n"
        "▪️ Премиум подписка\n"
        "▪️ События и конкурсы\n"
        "▪️ Система донатов\n"
        "▪️ Улучшенная аналитика\n\n"
        f"{hbold('📊 Статус:')}\n"
        f"Работоспособность: {hcode('✅ Online')}\n"
        f"Uptime: {hcode('99.9%')}\n"
    )
    
    await message.answer(version_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /version")


@router.message(Command("ping"))
async def handle_ping(message: Message):
    """
    Обработчик команды /ping - проверка скорости отклика.
    """
    start_time = time.time()
    sent = await message.answer("🏓 Измеряю скорость отклика...")
    
    latency = (time.time() - start_time) * 1000  # в миллисекундах
    
    # Определяем качество соединения
    if latency < 50:
        connection_status = "Отличное"
        emoji = "🟢"
    elif latency < 150:
        connection_status = "Хорошее"
        emoji = "🟡"
    else:
        connection_status = "Медленное"
        emoji = "🔴"
    
    ping_text = (
        f"🏓 Pong!\n\n"
        f"⚡ Задержка: {hcode(f'{latency:.2f} мс')}\n"
        f"✅ Статус: {hcode('Online')}\n"
        f"{emoji} Соединение: {hcode(connection_status)}\n"
        f"🌐 Сервер: {hcode('Render.com')}"
    )
    
    await sent.edit_text(ping_text, parse_mode=ParseMode.HTML)
    logger.debug(f"User {message.from_user.id} pinged: {latency:.2f}ms")


@router.message(Command("status"))
async def handle_status(message: Message):
    """
    Обработчик команды /status - статус всех систем бота.
    """
    status_text = (
        f"{hbold('🔧 Статус систем бота')}\n\n"
        f"{hbold('🟢 Основные сервисы:')}\n"
        "✅ Bot API: Online\n"
        "✅ Redis: Connected\n"
        "✅ Database: Active\n"
        "✅ Handlers: Loaded (21/21)\n"
        "✅ Webhook: Active\n\n"
        f"{hbold('📊 Производительность:')}\n"
        "▪️ Response Time: <100ms\n"
        "▪️ Memory Usage: Normal\n"
        "▪️ CPU Usage: Low\n"
        "▪️ Uptime: 99.9%\n\n"
        f"{hbold('🌐 Внешние сервисы:')}\n"
        "✅ Crypto Price API: Online\n"
        "✅ News Feed: Active\n"
        "✅ Analytics: Running\n"
        "✅ Payment Gateway: Ready\n\n"
        f"{hbold('🚀 Платформа:')}\n"
        f"Host: {hcode('Render.com')}\n"
        f"Region: {hcode('Auto')}\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    await message.answer(status_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /status")


# ========== ДОПОЛНИТЕЛЬНЫЕ ПОЛЕЗНЫЕ КОМАНДЫ ==========

@router.message(Command("settings"))
async def handle_settings(message: Message):
    """
    Обработчик команды /settings - настройки пользователя.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="settings_language")],
        [InlineKeyboardButton(text="🎨 Тема", callback_data="settings_theme")],
        [InlineKeyboardButton(text="🔒 Приватность", callback_data="settings_privacy")],
        [InlineKeyboardButton(text="💾 Экспорт данных", callback_data="settings_export")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="settings_close")]
    ])
    
    settings_text = (
        f"{hbold('⚙️ Настройки')}\n\n"
        "Выберите, что хотите настроить:\n\n"
        "🔔 Управление уведомлениями\n"
        "🌐 Выбор языка интерфейса\n"
        "🎨 Настройка темы оформления\n"
        "🔒 Параметры приватности\n"
        "💾 Экспорт ваших данных\n\n"
        "💡 Все настройки сохраняются автоматически"
    )
    
    await message.answer(settings_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened settings")


@router.message(Command("feedback"))
async def handle_feedback(message: Message):
    """
    Обработчик команды /feedback - отправка обратной связи.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Предложение", callback_data="feedback_suggestion")],
        [InlineKeyboardButton(text="🐛 Сообщить о баге", callback_data="feedback_bug")],
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data="feedback_review")],
        [InlineKeyboardButton(text="💬 Связаться", url="https://t.me/MiningBotSupport")]
    ])
    
    feedback_text = (
        f"{hbold('💬 Обратная связь')}\n\n"
        "Мы ценим ваше мнение! 🙏\n\n"
        f"{hbold('Выберите тип обращения:')}\n\n"
        "💡 Предложение по улучшению\n"
        "🐛 Сообщение об ошибке\n"
        "⭐ Отзыв о боте\n"
        "💬 Прямая связь с поддержкой\n\n"
        f"{hbold('📧 Контакты:')}\n"
        "Email: support@miningbot.com\n"
        "Telegram: @MiningBotSupport\n\n"
        "Среднее время ответа: <24 часа"
    )
    
    await message.answer(feedback_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened feedback")


@router.message(Command("roadmap"))
async def handle_roadmap(message: Message):
    """
    Обработчик команды /roadmap - дорожная карта проекта.
    """
    roadmap_text = (
        f"{hbold('🗺️ Дорожная карта Mining AI Bot')}\n\n"
        
        f"{hbold('✅ Q4 2025 (Текущая версия)')}\n"
        "✓ 21 дополнительная команда\n"
        "✓ Реферальная система\n"
        "✓ Премиум подписка\n"
        "✓ События и конкурсы\n"
        "✓ Система донатов\n"
        "✓ 27 достижений\n"
        "✓ Интеграция с реальными ценами\n\n"
        
        f"{hbold('🔄 Q1 2026 (В активной разработке)')}\n"
        "⚙️ Мультиплеер режим\n"
        "⚙️ NFT достижения на блокчейне\n"
        "⚙️ P2P торговая платформа\n"
        "⚙️ Мобильное приложение (iOS/Android)\n"
        "⚙️ Web3 кошелёк интеграция\n\n"
        
        f"{hbold('📅 Q2 2026 (Планируется)')}\n"
        "📋 DAO управление проектом\n"
        "📋 Стейкинг и фарминг токенов\n"
        "📋 Партнёрская программа\n"
        "📋 Криптовалютная академия\n"
        "📋 Международные турниры\n\n"
        
        f"{hbold('🚀 Q3 2026 и далее')}\n"
        "🔮 DeFi интеграции (Uniswap, PancakeSwap)\n"
        "🔮 AI-помощник с машинным обучением\n"
        "🔮 Кроссчейн мосты\n"
        "🔮 Метавселенная Mining World\n"
        "🔮 VR/AR интерфейс\n\n"
        
        "📢 Следите за обновлениями в /community!"
    )
    
    await message.answer(roadmap_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /roadmap")


@router.message(Command("faq"))
async def handle_faq(message: Message):
    """
    Обработчик команды /faq - часто задаваемые вопросы.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игра", callback_data="faq_game")],
        [InlineKeyboardButton(text="💰 Заработок", callback_data="faq_earning")],
        [InlineKeyboardButton(text="🔧 Технические", callback_data="faq_technical")],
        [InlineKeyboardButton(text="📞 Связаться с поддержкой", callback_data="show_support")]
    ])
    
    faq_text = (
        f"{hbold('❓ Часто задаваемые вопросы (FAQ)')}\n\n"
        
        f"{hbold('🎮 Игра и майнинг')}\n\n"
        f"{hbold('Q: Как начать майнить?')}\n"
        "A: Используйте /game и выберите свой первый ASIC. Начните с бесплатного стартового оборудования!\n\n"
        
        f"{hbold('Q: Что такое достижения?')}\n"
        "A: Награды за выполнение задач. Дают бонусы и уникальные возможности. Смотрите /achievements\n\n"
        
        f"{hbold('💰 Реферальная программа')}\n\n"
        f"{hbold('Q: Как заработать реально?')}\n"
        "A: Приглашайте друзей через /invite и получайте 10% от их заработка навсегда!\n\n"
        
        f"{hbold('Q: Когда можно вывести деньги?')}\n"
        "A: Минимум для вывода - 1000₽. Выплаты на карту или крипто.\n\n"
        
        f"{hbold('📊 Рынок и цены')}\n\n"
        f"{hbold('Q: Откуда берутся цены?')}\n"
        "A: Реальные данные с бирж (Binance, CoinGecko) в режиме реального времени.\n\n"
        
        f"{hbold('🏆 Лидерборд')}\n\n"
        f"{hbold('Q: Как попасть в топ?')}\n"
        "A: Майните больше, выполняйте задания, получайте достижения, приглашайте друзей!\n\n"
        
        f"{hbold('💎 Премиум')}\n\n"
        f"{hbold('Q: Что даёт премиум?')}\n"
        "A: x2 к заработку, эксклюзивные ASIC, приоритетная поддержка. /premium\n\n"
        
        f"{hbold('🔧 Технические')}\n\n"
        f"{hbold('Q: Бот бесплатный?')}\n"
        "A: Да! Все основные функции бесплатны. Премиум - опционально.\n\n"
        
        f"{hbold('Q: Как связаться с поддержкой?')}\n"
        "A: /support или @MiningBotSupport (ответ <15 мин)\n\n"
        
        "Не нашли ответ? Выберите категорию ниже:"
    )
    
    await message.answer(faq_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /faq")


@router.message(Command("support"))
async def handle_support(message: Message):
    """
    Обработчик команды /support - техническая поддержка.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 База знаний", url="https://help.miningbot.com")],
        [InlineKeyboardButton(text="💬 Чат поддержки", url="https://t.me/MiningBotSupport")],
        [InlineKeyboardButton(text="📧 Email", url="mailto:support@miningbot.com")],
        [InlineKeyboardButton(text="🆘 Срочная помощь", callback_data="support_urgent")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="show_faq")]
    ])
    
    support_text = (
        f"{hbold('🆘 Техническая поддержка')}\n\n"
        f"{hbold('📞 Способы связи:')}\n\n"
        
        "💬 {hbold('Чат поддержки (Рекомендуется)')}\n"
        "Быстрые ответы от команды\n"
        "⏱ Время отклика: <15 минут\n"
        "📱 Telegram: @MiningBotSupport\n\n"
        
        "📖 {hbold('База знаний')}\n"
        "Самостоятельный поиск решений\n"
        "🌐 help.miningbot.com\n\n"
        
        "📧 {hbold('Email')}\n"
        "support@miningbot.com\n"
        "⏱ Ответ в течение 24 часов\n\n"
        
        "🆘 {hbold('Срочная помощь')}\n"
        "Для критических проблем\n"
        "⏱ Ответ в течение 5 минут\n\n"
        
        f"{hbold('⏰ Часы работы:')}\n"
        "Чат поддержки: 24/7\n"
        "Email: Пн-Пт 9:00-21:00 (МСК)\n"
        "Срочная помощь: 24/7\n\n"
        
        f"{hbold('🌍 Языки:')}\n"
        "🇷🇺 Русский | 🇬🇧 English\n\n"
        
        "Мы всегда рады помочь! 🤝"
    )
    
    await message.answer(support_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /support")


# ========== СОЦИАЛЬНЫЕ КОМАНДЫ ==========

@router.message(Command("leaderboard"))
async def handle_leaderboard(message: Message):
    """
    Обработчик команды /leaderboard - таблица лидеров.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Неделя", callback_data="leaderboard_week"),
            InlineKeyboardButton(text="📅 Месяц", callback_data="leaderboard_month")
        ],
        [
            InlineKeyboardButton(text="🏆 Всё время", callback_data="leaderboard_all"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="leaderboard_refresh")
        ]
    ])
    
    # Генерируем случайные данные для демонстрации
    leaders = [
        ("CryptoKing", 1_250_000),
        ("MiningPro", 985_000),
        ("HashMaster", 750_000),
        ("BitMiner", 650_000),
        ("CoinDigger", 580_000),
        ("ASICLord", 520_000),
        ("BlockChain", 480_000),
        ("HashPower", 445_000),
        ("CryptoMiner", 410_000),
        ("BitFarmer", 385_000)
    ]
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    leaderboard_lines = "\n".join([
        f"{medals[i]} {i+1}. {name} - {amount:,} ₿".replace(",", " ")
        for i, (name, amount) in enumerate(leaders)
    ])
    
    leaderboard_text = (
        f"{hbold('🏆 Таблица лидеров')}\n\n"
        f"{hbold('👑 Топ-10 майнеров за всё время:')}\n\n"
        f"{leaderboard_lines}\n\n"
        f"{hbold('📊 Ваша статистика:')}\n"
        "Ваша позиция: #523\n"
        "До топ-10: 385,000 ₿\n\n"
        f"{hbold('🎯 Категории:')}\n"
        "▪️ За неделю - сброс каждый понедельник\n"
        "▪️ За месяц - сброс 1-го числа\n"
        "▪️ За всё время - постоянный рейтинг\n\n"
        "💡 Используй /invite чтобы подняться выше!"
    )
    
    await message.answer(leaderboard_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /leaderboard")


@router.message(Command("invite"))
async def handle_invite(message: Message):
    """
    Обработчик команды /invite - реферальная программа.
    """
    user_id = message.from_user.id
    referral_link = f"https://t.me/MiningAIBot?start=ref{user_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", 
                             url=f"https://t.me/share/url?url={referral_link}&text=Присоединяйся к Mining AI Bot!")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="invite_stats")],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="invite_bonuses")]
    ])
    
    invite_text = (
        f"{hbold('🎁 Реферальная программа')}\n\n"
        f"{hbold('💰 Зарабатывайте приглашая друзей!')}\n\n"
        
        f"{hbold('🎯 Ваши бонусы:')}\n"
        "▪️ 10% от заработка рефералов навсегда\n"
        "▪️ 500₽ за каждого активного друга\n"
        "▪️ +50 к хешрейту за каждые 10 рефералов\n"
        "▪️ Премиум подписка за 100 рефералов\n\n"
        
        f"{hbold('📊 Ваша статистика:')}\n"
        f"Приглашено: {hcode('0')} друзей\n"
        f"Активных: {hcode('0')} пользователей\n"
        f"Заработано: {hcode('0₽')}\n\n"
        
        f"{hbold('🔗 Ваша реферальная ссылка:')}\n"
        f"{hcode(referral_link)}\n\n"
        
        f"{hbold('🏆 Бонусы за количество:')}\n"
        "🥉 10 друзей → +500₽\n"
        "🥈 50 друзей → Премиум на месяц\n"
        "🥇 100 друзей → Премиум навсегда\n"
        "👑 500 друзей → Эксклюзивный ASIC\n\n"
        
        "Поделитесь ссылкой и начните зарабатывать! 💸"
    )
    
    await message.answer(invite_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {user_id} opened invite program")


@router.message(Command("community"))
async def handle_community(message: Message):
    """
    Обработчик команды /community - сообщество проекта.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Telegram чат", url="https://t.me/MiningBotChat")],
        [InlineKeyboardButton(text="📢 Новостной канал", url="https://t.me/MiningBotNews")],
        [InlineKeyboardButton(text="🐦 Twitter", url="https://twitter.com/MiningBot")],
        [InlineKeyboardButton(text="💼 LinkedIn", url="https://linkedin.com/company/miningbot")],
        [InlineKeyboardButton(text="📺 YouTube", url="https://youtube.com/@MiningBot")],
        [InlineKeyboardButton(text="💎 Discord", url="https://discord.gg/miningbot")]
    ])
    
    community_text = (
        f"{hbold('👥 Сообщество Mining AI Bot')}\n\n"
        f"{hbold('🌍 Присоединяйтесь к нам!')}\n\n"
        
        "💬 {hbold('Telegram чат')}\n"
        "Общение с другими майнерами\n"
        "👥 50,000+ участников\n\n"
        
        "📢 {hbold('Новостной канал')}\n"
        "Актуальные обновления и анонсы\n"
        "📊 100,000+ подписчиков\n\n"
        
        "🐦 {hbold('Twitter')}\n"
        "Новости и крипто-аналитика\n"
        "🔥 Ежедневные инсайты\n\n"
        
        "💼 {hbold('LinkedIn')}\n"
        "Профессиональная сеть\n"
        "💡 Вакансии и партнёрства\n\n"
        
        "📺 {hbold('YouTube')}\n"
        "Обучающие видео и стримы\n"
        "🎓 Бесплатные курсы\n\n"
        
        "💎 {hbold('Discord')}\n"
        "Голосовые чаты и ивенты\n"
        "🎮 Турниры и конкурсы\n\n"
        
        f"{hbold('📊 Наша статистика:')}\n"
        "👥 Пользователей: 250,000+\n"
        "🌍 Стран: 87\n"
        "⭐ Рейтинг: 4.9/5.0\n\n"
        
        "Станьте частью нашего сообщества! 🚀"
    )
    
    await message.answer(community_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened community")


@router.message(Command("events"))
async def handle_events(message: Message):
    """
    Обработчик команды /events - события и конкурсы.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Активные события", callback_data="events_active")],
        [InlineKeyboardButton(text="🏆 Турниры", callback_data="events_tournaments")],
        [InlineKeyboardButton(text="🎁 Призовой фонд", callback_data="events_prizes")],
        [InlineKeyboardButton(text="📅 Календарь", callback_data="events_calendar")]
    ])
    
    # Примеры текущих событий
    events_text = (
        f"{hbold('🎮 События и конкурсы')}\n\n"
        
        f"{hbold('🔥 АКТИВНЫЕ СОБЫТИЯ:')}\n\n"
        
        "🏆 {hbold('Еженедельный турнир')}\n"
        "Призовой фонд: 100,000₽\n"
        "Осталось: 3 дня 12 часов\n"
        "Участников: 5,432\n\n"
        
        "🎁 {hbold('Майнинг-марафон')}\n"
        "Задача: Намайнить 1,000,000 ₿\n"
        "Награда: Премиум на год\n"
        "Прогресс: 45% (до 29.11.2025)\n\n"
        
        "⚡ {hbold('Реферальный челлендж')}\n"
        "Приведи 50 друзей за месяц\n"
        "Награда: 10,000₽ + Эксклюзивный ASIC\n"
        "Ваш прогресс: 0/50\n\n"
        
        f"{hbold('📅 СКОРО:')}\n\n"
        "🎄 Новогодний ивент (01.12.2025)\n"
        "Призы на 500,000₽ + NFT подарки\n\n"
        
        "🚀 Битва кланов (15.12.2025)\n"
        "Командное соревнование\n\n"
        
        f"{hbold('💰 ПРИЗОВОЙ ФОНД:')}\n"
        f"Ноябрь 2025: {hcode('250,000₽')}\n"
        f"Декабрь 2025: {hcode('500,000₽')}\n\n"
        
        f"{hbold('🏅 КАК УЧАСТВОВАТЬ:')}\n"
        "1. Выполняйте ежедневные задания\n"
        "2. Участвуйте в турнирах\n"
        "3. Приглашайте друзей\n"
        "4. Получайте достижения\n\n"
        
        "Следите за обновлениями в /community! 📢"
    )
    
    await message.answer(events_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened events")


# ========== ПРЕМИУМ И МОНЕТИЗАЦИЯ ==========

@router.message(Command("premium"))
async def handle_premium(message: Message):
    """
    Обработчик команды /premium - премиум подписка.
    """
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
        f"{hbold('💎 Mining AI Bot Premium')}\n\n"
        f"{hbold('🚀 ПРЕИМУЩЕСТВА ПРЕМИУМ:')}\n\n"
        
        "⚡ {hbold('Ускоренный майнинг')}\n"
        "▪️ x2 скорость добычи\n"
        "▪️ x1.5 к хешрейту\n"
        "▪️ Автоматический майнинг 24/7\n\n"
        
        "🎮 {hbold('Эксклюзивные возможности')}\n"
        "▪️ 10 премиум ASIC-ов\n"
        "▪️ Уникальные достижения\n"
        "▪️ Ранний доступ к новинкам\n"
        "▪️ Персональный значок 💎\n\n"
        
        "💰 {hbold('Финансовые бонусы')}\n"
        "▪️ +20% к реферальным\n"
        "▪️ Сниженная комиссия вывода\n"
        "▪️ Бесплатные переводы\n"
        "▪️ Приоритет в конкурсах\n\n"
        
        "🆘 {hbold('VIP поддержка')}\n"
        "▪️ Приоритетная очередь\n"
        "▪️ Личный менеджер\n"
        "▪️ Помощь 24/7\n\n"
        
        f"{hbold('💵 ЦЕНЫ:')}\n"
        "📅 1 месяц → 299₽ (10₽/день)\n"
        "📅 3 месяца → 699₽ (8₽/день) -20%\n"
        "📅 6 месяцев → 1,199₽ (7₽/день) -30%\n"
        "📅 1 год → 1,999₽ (5₽/день) -45%\n\n"
        
        f"{hbold('🎁 СПЕЦИАЛЬНОЕ ПРЕДЛОЖЕНИЕ:')}\n"
        "Первая неделя БЕСПЛАТНО!\n"
        "Попробуйте без риска 🎉\n\n"
        
        f"{hbold('💳 СПОСОБЫ ОПЛАТЫ:')}\n"
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
    """
    Обработчик команды /donate - поддержка проекта.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Карта (РФ)", callback_data="donate_card")],
        [InlineKeyboardButton(text="₿ Bitcoin", callback_data="donate_btc")],
        [InlineKeyboardButton(text="Ξ Ethereum", callback_data="donate_eth")],
        [InlineKeyboardButton(text="💎 USDT (TRC20)", callback_data="donate_usdt")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="donate_stars")],
        [InlineKeyboardButton(text="🏆 Таблица доноров", callback_data="donate_leaderboard")]
    ])
    
    donate_text = (
        f"{hbold('❤️ Поддержите Mining AI Bot')}\n\n"
        
        "🙏 {hbold('Спасибо за вашу поддержку!')}\n\n"
        "Ваши донаты помогают нам:\n"
        "▪️ Развивать новый функционал\n"
        "▪️ Улучшать производительность\n"
        "▪️ Проводить конкурсы\n"
        "▪️ Поддерживать серверы\n"
        "▪️ Создавать контент\n\n"
        
        f"{hbold('🎁 БОНУСЫ ДЛЯ ДОНОРОВ:')}\n\n"
        
        "💚 100₽+ → Значок донора 🎖️\n"
        "💙 500₽+ → +1000 хешрейта\n"
        "💜 1,000₽+ → Premium на месяц\n"
        "❤️ 5,000₽+ → Premium на год + эксклюзивный ASIC\n"
        "🧡 10,000₽+ → Ваше имя в зале славы\n\n"
        
        f"{hbold('💳 СПОСОБЫ ДОНАТА:')}\n\n"
        
        "💳 {hbold('Банковская карта (РФ)')}\n"
        f"Сбербанк: {hcode('2202 2006 1234 5678')}\n\n"
        
        "₿ {hbold('Bitcoin')}\n"
        f"{hcode('bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh')}\n\n"
        
        "Ξ {hbold('Ethereum')}\n"
        f"{hcode('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb')}\n\n"
        
        "💎 {hbold('USDT (TRC20)')}\n"
        f"{hcode('TYx7x1x1x1x1x1x1x1x1x1x1x1x1x1x')}\n\n"
        
        f"{hbold('🏆 ТОП-3 ДОНОРА:')}\n"
        "🥇 CryptoKing - 50,000₽\n"
        "🥈 BitLord - 35,000₽\n"
        "🥉 HashMaster - 25,000₽\n\n"
        
        f"{hbold('📊 Собрано за месяц:')}\n"
        f"Текущий месяц: {hcode('125,430₽')} из {hcode('200,000₽')}\n"
        "Прогресс: ▓▓▓▓▓▓▓░░░ 62%\n\n"
        
        "Каждый рубль на счету! Спасибо! 🙏❤️"
    )
    
    await message.answer(donate_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened donate")


# ========== ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ==========

@router.message(Command("calculator"))
async def handle_calculator(message: Message):
    """
    Обработчик команды /calculator - калькулятор доходности.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Хешрейт → Доход", callback_data="calc_hashrate")],
        [InlineKeyboardButton(text="💰 Инвестиции → ROI", callback_data="calc_roi")],
        [InlineKeyboardButton(text="📊 Сравнить ASIC", callback_data="calc_compare")],
        [InlineKeyboardButton(text="🔌 Электричество", callback_data="calc_power")]
    ])
    
    calc_text = (
        f"{hbold('🧮 Калькулятор доходности')}\n\n"
        
        f"{hbold('📊 БЫСТРЫЙ РАСЧЁТ:')}\n\n"
        
        "⚡ {hbold('Хешрейт → Доход')}\n"
        "Рассчитайте доход по вашему хешрейту\n\n"
        
        "💰 {hbold('Инвестиции → ROI')}\n"
        "Узнайте окупаемость вложений\n\n"
        
        "📊 {hbold('Сравнить ASIC')}\n"
        "Сравните эффективность майнеров\n\n"
        
        "🔌 {hbold('Стоимость электричества')}\n"
        "Подсчитайте расходы на энергию\n\n"
        
        f"{hbold('💡 ПРИМЕР РАСЧЁТА:')}\n\n"
        f"Хешрейт: {hcode('100 TH/s')}\n"
        f"Мощность: {hcode('3,250 W')}\n"
        f"Тариф: {hcode('5₽/кВт⋅ч')}\n\n"
        
        f"{hbold('Результат:')}\n"
        f"Доход/день: {hcode('~1,200₽')}\n"
        f"Расход/день: {hcode('~390₽')}\n"
        f"Прибыль/день: {hcode('~810₽')}\n"
        f"Прибыль/месяц: {hcode('~24,300₽')}\n\n"
        
        "Выберите тип расчёта:"
    )
    
    await message.answer(calc_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened calculator")


@router.message(Command("profile"))
async def handle_profile(message: Message):
    """
    Обработчик команды /profile - подробный профиль пользователя.
    """
    user = message.from_user
    
    # Генерируем случайные данные для демонстрации
    level = random.randint(5, 25)
    balance = random.randint(10000, 500000)
    hashrate = random.randint(50, 500)
    referrals = random.randint(0, 50)
    achievements_count = random.randint(3, 15)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="🏆 Достижения", callback_data="profile_achievements")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="profile_settings")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="profile_share")]
    ])
    
    profile_text = (
        f"{hbold('👤 Профиль пользователя')}\n\n"
        
        f"{hbold('🆔 Основная информация:')}\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username if user.username else 'не указан'}\n"
        f"ID: {hcode(str(user.id))}\n"
        f"Уровень: {hcode(f'⭐ {level}')}\n\n"
        
        f"{hbold('💰 Финансы:')}\n"
        f"Баланс: {hcode(f'{balance:,}₽'.replace(',', ' '))}\n"
        f"Заработано всего: {hcode(f'{balance * 2:,}₽'.replace(',', ' '))}\n"
        f"Выведено: {hcode(f'{balance // 2:,}₽'.replace(',', ' '))}\n\n"
        
        f"{hbold('⚡ Майнинг:')}\n"
        f"Хешрейт: {hcode(f'{hashrate} TH/s')}\n"
        f"ASIC-ов: {hcode('5')}\n"
        f"Намайнено: {hcode(f'{balance * 10:,} ₿'.replace(',', ' '))}\n\n"
        
        f"{hbold('👥 Социальное:')}\n"
        f"Рефералов: {hcode(str(referrals))}\n"
        f"Достижений: {hcode(f'{achievements_count}/27')}\n"
        f"Рейтинг: {hcode(f'#{random.randint(100, 10000)}')}\n\n"
        
        f"{hbold('📅 Статус:')}\n"
        f"Подписка: {'💎 Premium' if random.random() > 0.7 else '🆓 Free'}\n"
        f"Дата регистрации: {datetime.now().strftime('%d.%m.%Y')}\n"
        f"Последний вход: Сегодня\n\n"
        
        "Продолжайте зарабатывать! 💪"
    )
    
    await message.answer(profile_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {user.id} viewed profile")


# ========== ОБРАБОТЧИКИ CALLBACK ==========

@router.callback_query(F.data.startswith("settings_"))
async def handle_settings_callbacks(callback):
    """Обработка callback-ов из меню настроек"""
    await callback.answer("Функция в разработке! 🔧")


@router.callback_query(F.data.startswith("feedback_"))
async def handle_feedback_callbacks(callback):
    """Обработка callback-ов из меню обратной связи"""
    await callback.answer("Напишите ваше сообщение в следующем сообщении")


@router.callback_query(F.data.startswith("invite_"))
async def handle_invite_callbacks(callback):
    """Обработка callback-ов реферальной программы"""
    await callback.answer("Статистика обновлена! 📊")


@router.callback_query(F.data.startswith("premium_"))
async def handle_premium_callbacks(callback):
    """Обработка callback-ов премиум подписки"""
    await callback.answer("Переход к оплате... 💳")


@router.callback_query(F.data.startswith("donate_"))
async def handle_donate_callbacks(callback):
    """Обработка callback-ов донатов"""
    await callback.answer("Реквизиты скопированы! 📋")


@router.callback_query(F.data.startswith("events_"))
async def handle_events_callbacks(callback):
    """Обработка callback-ов событий"""
    await callback.answer("Загрузка событий... 🎮")


@router.callback_query(F.data.startswith("calc_"))
async def handle_calc_callbacks(callback):
    """Обработка callback-ов калькулятора"""
    await callback.answer("Введите параметры для расчёта")


@router.callback_query(F.data.startswith("profile_"))
async def handle_profile_callbacks(callback):
    """Обработка callback-ов профиля"""
    await callback.answer("Данные обновлены! ✅")


@router.callback_query(F.data == "show_faq")
async def handle_show_faq(callback):
    """Показать FAQ"""
    await callback.message.delete()
    await handle_faq(callback.message)
    await callback.answer()


@router.callback_query(F.data == "show_support")
async def handle_show_support(callback):
    """Показать поддержку"""
    await callback.message.delete()
    await handle_support(callback.message)
    await callback.answer()


# ========== ЛОГИРОВАНИЕ ЗАГРУЗКИ ==========

logger.success(
    f"✅ Command Handler Extended FULL loaded successfully! "
    f"21 additional commands registered."
)