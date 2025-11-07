# bot/handlers/public/commands/tools.py
"""
Инструменты и калькуляторы.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from loguru import logger

router = Router(name="tools_commands_router")


@router.message(Command("calculator"))
async def handle_calculator(message: Message):
    """
    Обработчик команды /calculator - калькулятор доходности майнинга.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Хешрейт → Доход", callback_data="calc_hashrate")],
        [InlineKeyboardButton(text="💰 Инвестиции → ROI", callback_data="calc_roi")],
        [InlineKeyboardButton(text="📊 Сравнить ASIC", callback_data="calc_compare")],
        [InlineKeyboardButton(text="🔌 Электричество", callback_data="calc_power")],
        [InlineKeyboardButton(text="🧮 Универсальный калькулятор", callback_data="calc_universal")]
    ])
    
    calc_text = (
        f"<b>🧮 Калькулятор доходности майнинга</b>\n\n"
        
        f"<b>📊 ДОСТУПНЫЕ РАСЧЁТЫ:</b>\n\n"
        
        "⚡ <b>Хешрейт → Доход</b>\n"
        "Рассчитайте доход по вашему хешрейту\n"
        "Пример: 100 TH/s → сколько заработаю?\n\n"
        
        "💰 <b>Инвестиции → ROI</b>\n"
        "Узнайте окупаемость вложений\n"
        "Пример: купил ASIC за 500,000₽ → когда окупится?\n\n"
        
        "📊 <b>Сравнить ASIC</b>\n"
        "Сравните эффективность майнеров\n"
        "Пример: Antminer S19 vs WhatsMiner M30S\n\n"
        
        "🔌 <b>Стоимость электричества</b>\n"
        "Подсчитайте расходы на энергию\n"
        "Пример: 3000W × 5₽/кВт⋅ч = сколько в месяц?\n\n"
        
        "🧮 <b>Универсальный калькулятор</b>\n"
        "Комплексный расчёт с учётом всех параметров\n\n"
        
        f"<b>💡 ПРИМЕР БЫСТРОГО РАСЧЁТА:</b>\n\n"
        f"Хешрейт: <code>100 TH/s</code>\n"
        f"Мощность: <code>3,250 W</code>\n"
        f"Тариф: <code>5₽/кВт⋅ч</code>\n"
        f"Цена BTC: <code>6,000,000₽</code>\n\n"
        
        f"<b>📈 Результат:</b>\n"
        f"Доход/день: <code>~1,200₽</code>\n"
        f"Расход/день: <code>~390₽</code>\n"
        f"Прибыль/день: <code>~810₽</code>\n"
        f"Прибыль/месяц: <code>~24,300₽</code>\n"
        f"Окупаемость: <code>~20 месяцев</code>\n\n"
        
        f"<b>🎯 КАК ПОЛЬЗОВАТЬСЯ:</b>\n"
        "1. Выберите тип расчёта\n"
        "2. Введите свои данные\n"
        "3. Получите детальный результат\n"
        "4. Сохраните расчёт для истории\n\n"
        
        f"<b>💡 СОВЕТЫ:</b>\n"
        "▪️ Учитывайте рост сложности сети\n"
        "▪️ Считайте резерв на ремонт (5-10%)\n"
        "▪️ Не забывайте про охлаждение\n"
        "▪️ Проверяйте актуальные цены\n\n"
        
        "Выберите тип расчёта ⬇️"
    )
    
    await message.answer(calc_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened calculator")


@router.message(Command("profile"))
async def handle_profile(message: Message):
    """Обработчик команды /profile."""
    import random
    from datetime import datetime
    
    user = message.from_user
    
    level = random.randint(5, 25)
    balance = random.randint(10000, 500000)
    hashrate = random.randint(50, 500)
    referrals = random.randint(0, 50)
    achievements_count = random.randint(3, 15)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="🏆 Достижения", callback_data="profile_achievements")],
        [InlineKeyboardButton(text="🧮 Калькулятор", callback_data="calc_universal")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="profile_settings")]
    ])
    
    profile_text = (
        f"<b>👤 Профиль пользователя</b>\n\n"
        
        f"<b>🆔 Основная информация:</b>\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username if user.username else 'не указан'}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Уровень: <code>⭐ {level}</code>\n\n"
        
        f"<b>💰 Финансы:</b>\n"
        f"Баланс: <code>{balance:,}₽</code>\n"
        f"Заработано всего: <code>{balance * 2:,}₽</code>\n"
        f"Выведено: <code>{balance // 2:,}₽</code>\n\n"
        
        f"<b>⚡ Майнинг:</b>\n"
        f"Хешрейт: <code>{hashrate} TH/s</code>\n"
        f"ASIC-ов: <code>5</code>\n"
        f"Намайнено: <code>{balance * 10:,} ₿</code>\n\n"
        
        f"<b>👥 Социальное:</b>\n"
        f"Рефералов: <code>{referrals}</code>\n"
        f"Достижений: <code>{achievements_count}/27</code>\n"
        f"Рейтинг: <code>#{random.randint(100, 10000)}</code>\n\n"
        
        f"<b>📅 Статус:</b>\n"
        f"Подписка: {'💎 Premium' if random.random() > 0.7 else '🆓 Free'}\n"
        f"Дата регистрации: {datetime.now().strftime('%d.%m.%Y')}\n"
        f"Последний вход: Сегодня\n\n"
        
        "💡 Используй /calculator для расчёта доходности!"
    )
    
    await message.answer(profile_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {user.id} viewed profile")