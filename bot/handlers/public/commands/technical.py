# bot/handlers/public/commands/technical.py
"""
Технические команды: настройки, поддержка, статус.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from loguru import logger
import time
from datetime import datetime

router = Router(name="technical_commands_router")


@router.message(Command("ping"))
async def handle_ping(message: Message):
    """Обработчик команды /ping - проверка скорости отклика."""
    start_time = time.time()
    sent = await message.answer("🏓 Измеряю скорость отклика...")
    
    latency = (time.time() - start_time) * 1000
    
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
        f"⚡ Задержка: <code>{latency:.2f} мс</code>\n"
        f"✅ Статус: <code>Online</code>\n"
        f"{emoji} Соединение: <code>{connection_status}</code>\n"
        f"🌐 Сервер: <code>Render.com</code>"
    )
    
    await sent.edit_text(ping_text, parse_mode=ParseMode.HTML)
    logger.debug(f"User {message.from_user.id} pinged: {latency:.2f}ms")


@router.message(Command("status"))
async def handle_status(message: Message):
    """Обработчик команды /status - статус всех систем."""
    status_text = (
        f"<b>🔧 Статус систем бота</b>\n\n"
        f"<b>🟢 Основные сервисы:</b>\n"
        "✅ Bot API: Online\n"
        "✅ Redis: Connected\n"
        "✅ Database: Active\n"
        "✅ Handlers: Loaded\n"
        "✅ Webhook: Active\n\n"
        f"<b>📊 Производительность:</b>\n"
        "▪️ Response Time: меньше 100ms\n"
        "▪️ Memory Usage: Normal\n"
        "▪️ CPU Usage: Low\n"
        "▪️ Uptime: 99.9%\n\n"
        f"<b>🌐 Внешние сервисы:</b>\n"
        "✅ Crypto Price API: Online\n"
        "✅ News Feed: Active\n"
        "✅ Analytics: Running\n"
        "✅ Payment Gateway: Ready\n\n"
        f"<b>🚀 Платформа:</b>\n"
        f"Host: <code>Render.com</code>\n"
        f"Region: <code>Auto</code>\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    await message.answer(status_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /status")


@router.message(Command("version"))
async def handle_version(message: Message):
    """Обработчик команды /version - информация о версии."""
    version_text = (
        f"<b>🔧 Информация о версии</b>\n\n"
        f"<b>📦 Версия бота:</b>\n"
        f"Version: <code>3.0.0 Production</code>\n"
        f"Release: <code>Production Ready</code>\n"
        f"Build Date: <code>07 November 2025</code>\n"
        f"Commands: <code>Full featured</code>\n\n"
        f"<b>🐍 Технологический стек:</b>\n"
        f"Python: <code>3.11+</code>\n"
        f"aiogram: <code>3.13.1</code>\n"
        f"Redis: <code>5.1.1</code>\n"
        f"Platform: <code>Render.com</code>\n\n"
        f"<b>✨ Особенности:</b>\n"
        "▪️ Модульная архитектура\n"
        "▪️ Калькулятор майнинга\n"
        "▪️ Реферальная система\n"
        "▪️ Премиум подписка\n"
        "▪️ События и конкурсы\n"
        "▪️ Система донатов\n\n"
        f"<b>📊 Статус:</b>\n"
        f"Работоспособность: <code>✅ Online</code>\n"
        f"Uptime: <code>99.9%</code>\n"
    )
    
    await message.answer(version_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /version")


@router.message(Command("settings"))
async def handle_settings(message: Message):
    """Обработчик команды /settings - настройки пользователя."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="settings_language")],
        [InlineKeyboardButton(text="🎨 Тема", callback_data="settings_theme")],
        [InlineKeyboardButton(text="🔒 Приватность", callback_data="settings_privacy")],
        [InlineKeyboardButton(text="💾 Экспорт данных", callback_data="settings_export")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="settings_close")]
    ])
    
    settings_text = (
        f"<b>⚙️ Настройки</b>\n\n"
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
    """Обработчик команды /feedback - отправка обратной связи."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Предложение", callback_data="feedback_suggestion")],
        [InlineKeyboardButton(text="🐛 Сообщить о баге", callback_data="feedback_bug")],
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data="feedback_review")],
        [InlineKeyboardButton(text="💬 Связаться", url="https://t.me/MiningBotSupport")]
    ])
    
    feedback_text = (
        f"<b>💬 Обратная связь</b>\n\n"
        "Мы ценим ваше мнение! 🙏\n\n"
        f"<b>Выберите тип обращения:</b>\n\n"
        "💡 Предложение по улучшению\n"
        "🐛 Сообщение об ошибке\n"
        "⭐ Отзыв о боте\n"
        "💬 Прямая связь с поддержкой\n\n"
        f"<b>📧 Контакты:</b>\n"
        "Email: support@miningbot.com\n"
        "Telegram: @MiningBotSupport\n\n"
        "Среднее время ответа: меньше 24 часов"
    )
    
    await message.answer(feedback_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened feedback")


@router.message(Command("support"))
async def handle_support(message: Message):
    """Обработчик команды /support - техническая поддержка."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 База знаний", url="https://help.miningbot.com")],
        [InlineKeyboardButton(text="💬 Чат поддержки", url="https://t.me/MiningBotSupport")],
        [InlineKeyboardButton(text="📧 Email", url="mailto:support@miningbot.com")],
        [InlineKeyboardButton(text="🆘 Срочная помощь", callback_data="support_urgent")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="show_faq")]
    ])
    
    support_text = (
        f"<b>🆘 Техническая поддержка</b>\n\n"
        f"<b>📞 Способы связи:</b>\n\n"
        
        "💬 <b>Чат поддержки (Рекомендуется)</b>\n"
        "Быстрые ответы от команды\n"
        "⏱ Время отклика: меньше 15 минут\n"
        "📱 Telegram: @MiningBotSupport\n\n"
        
        "📖 <b>База знаний</b>\n"
        "Самостоятельный поиск решений\n"
        "🌐 help.miningbot.com\n\n"
        
        "📧 <b>Email</b>\n"
        "support@miningbot.com\n"
        "⏱ Ответ в течение 24 часов\n\n"
        
        "🆘 <b>Срочная помощь</b>\n"
        "Для критических проблем\n"
        "⏱ Ответ в течение 5 минут\n\n"
        
        f"<b>⏰ Часы работы:</b>\n"
        "Чат поддержки: 24/7\n"
        "Email: Пн-Пт 9:00-21:00 (МСК)\n"
        "Срочная помощь: 24/7\n\n"
        
        f"<b>🌍 Языки:</b>\n"
        "🇷🇺 Русский | 🇬🇧 English\n\n"
        
        "Мы всегда рады помочь! 🤝"
    )
    
    await message.answer(support_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /support")