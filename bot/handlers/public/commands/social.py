# bot/handlers/public/commands/social.py
"""
Социальные команды: рефералы, сообщество, события.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from loguru import logger
import random

router = Router(name="social_commands_router")


@router.message(Command("invite"))
async def handle_invite(message: Message):
    """Обработчик команды /invite - реферальная программа."""
    user_id = message.from_user.id
    referral_link = f"https://t.me/MiningAIBot?start=ref{user_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться ссылкой", 
            url=f"https://t.me/share/url?url={referral_link}&text=Присоединяйся к Mining AI Bot!"
        )],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="invite_stats")],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="invite_bonuses")]
    ])
    
    invite_text = (
        f"<b>🎁 Реферальная программа</b>\n\n"
        f"<b>💰 Зарабатывайте приглашая друзей!</b>\n\n"
        
        f"<b>🎯 Ваши бонусы:</b>\n"
        "▪️ 10% от заработка рефералов навсегда\n"
        "▪️ 500₽ за каждого активного друга\n"
        "▪️ +50 к хешрейту за каждые 10 рефералов\n"
        "▪️ Премиум подписка за 100 рефералов\n\n"
        
        f"<b>📊 Ваша статистика:</b>\n"
        f"Приглашено: <code>0</code> друзей\n"
        f"Активных: <code>0</code> пользователей\n"
        f"Заработано: <code>0₽</code>\n\n"
        
        f"<b>🔗 Ваша реферальная ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        
        f"<b>🏆 Бонусы за количество:</b>\n"
        "🥉 10 друзей → +500₽\n"
        "🥈 50 друзей → Премиум на месяц\n"
        "🥇 100 друзей → Премиум навсегда\n"
        "👑 500 друзей → Эксклюзивный ASIC\n\n"
        
        "Поделитесь ссылкой и начните зарабатывать! 💸"
    )
    
    await message.answer(invite_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {user_id} opened invite program")


@router.message(Command("leaderboard"))
async def handle_leaderboard(message: Message):
    """Обработчик команды /leaderboard - таблица лидеров."""
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
        f"<b>🏆 Таблица лидеров</b>\n\n"
        f"<b>👑 Топ-10 майнеров за всё время:</b>\n\n"
        f"{leaderboard_lines}\n\n"
        f"<b>📊 Ваша статистика:</b>\n"
        "Ваша позиция: #523\n"
        "До топ-10: 385,000 ₿\n\n"
        f"<b>🎯 Категории:</b>\n"
        "▪️ За неделю - сброс каждый понедельник\n"
        "▪️ За месяц - сброс 1-го числа\n"
        "▪️ За всё время - постоянный рейтинг\n\n"
        "💡 Используй /invite чтобы подняться выше!"
    )
    
    await message.answer(leaderboard_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} requested /leaderboard")


@router.message(Command("community"))
async def handle_community(message: Message):
    """Обработчик команды /community - сообщество проекта."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Telegram чат", url="https://t.me/MiningBotChat")],
        [InlineKeyboardButton(text="📢 Новостной канал", url="https://t.me/MiningBotNews")],
        [InlineKeyboardButton(text="🐦 Twitter", url="https://twitter.com/MiningBot")],
        [InlineKeyboardButton(text="💼 LinkedIn", url="https://linkedin.com/company/miningbot")],
        [InlineKeyboardButton(text="📺 YouTube", url="https://youtube.com/@MiningBot")],
        [InlineKeyboardButton(text="💎 Discord", url="https://discord.gg/miningbot")]
    ])
    
    community_text = (
        f"<b>👥 Сообщество Mining AI Bot</b>\n\n"
        f"<b>🌍 Присоединяйтесь к нам!</b>\n\n"
        
        "💬 <b>Telegram чат</b>\n"
        "Общение с другими майнерами\n"
        "👥 50,000+ участников\n\n"
        
        "📢 <b>Новостной канал</b>\n"
        "Актуальные обновления и анонсы\n"
        "📊 100,000+ подписчиков\n\n"
        
        "🐦 <b>Twitter</b>\n"
        "Новости и крипто-аналитика\n"
        "🔥 Ежедневные инсайты\n\n"
        
        "💼 <b>LinkedIn</b>\n"
        "Профессиональная сеть\n"
        "💡 Вакансии и партнёрства\n\n"
        
        "📺 <b>YouTube</b>\n"
        "Обучающие видео и стримы\n"
        "🎓 Бесплатные курсы\n\n"
        
        "💎 <b>Discord</b>\n"
        "Голосовые чаты и ивенты\n"
        "🎮 Турниры и конкурсы\n\n"
        
        f"<b>📊 Наша статистика:</b>\n"
        "👥 Пользователей: 250,000+\n"
        "🌍 Стран: 87\n"
        "⭐ Рейтинг: 4.9/5.0\n\n"
        
        "Станьте частью нашего сообщества! 🚀"
    )
    
    await message.answer(community_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened community")


@router.message(Command("events"))
async def handle_events(message: Message):
    """Обработчик команды /events - события и конкурсы."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Активные события", callback_data="events_active")],
        [InlineKeyboardButton(text="🏆 Турниры", callback_data="events_tournaments")],
        [InlineKeyboardButton(text="🎁 Призовой фонд", callback_data="events_prizes")],
        [InlineKeyboardButton(text="📅 Календарь", callback_data="events_calendar")]
    ])
    
    events_text = (
        f"<b>🎮 События и конкурсы</b>\n\n"
        
        f"<b>🔥 АКТИВНЫЕ СОБЫТИЯ:</b>\n\n"
        
        "🏆 <b>Еженедельный турнир</b>\n"
        "Призовой фонд: 100,000₽\n"
        "Осталось: 3 дня 12 часов\n"
        "Участников: 5,432\n\n"
        
        "🎁 <b>Майнинг-марафон</b>\n"
        "Задача: Намайнить 1,000,000 ₿\n"
        "Награда: Премиум на год\n"
        "Прогресс: 45% (до 29.11.2025)\n\n"
        
        "⚡ <b>Реферальный челлендж</b>\n"
        "Приведи 50 друзей за месяц\n"
        "Награда: 10,000₽ + Эксклюзивный ASIC\n"
        "Ваш прогресс: 0/50\n\n"
        
        f"<b>📅 СКОРО:</b>\n\n"
        "🎄 Новогодний ивент (01.12.2025)\n"
        "Призы на 500,000₽ + NFT подарки\n\n"
        
        "🚀 Битва кланов (15.12.2025)\n"
        "Командное соревнование\n\n"
        
        f"<b>💰 ПРИЗОВОЙ ФОНД:</b>\n"
        f"Ноябрь 2025: <code>250,000₽</code>\n"
        f"Декабрь 2025: <code>500,000₽</code>\n\n"
        
        f"<b>🏅 КАК УЧАСТВОВАТЬ:</b>\n"
        "1. Выполняйте ежедневные задания\n"
        "2. Участвуйте в турнирах\n"
        "3. Приглашайте друзей\n"
        "4. Получайте достижения\n\n"
        
        "Следите за обновлениями в /community! 📢"
    )
    
    await message.answer(events_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    logger.info(f"User {message.from_user.id} opened events")


@router.message(Command("stats"))
async def handle_stats(message: Message):
    """Обработчик команды /stats - расширенная статистика."""
    from datetime import datetime
    
    user = message.from_user
    user_id = user.id
    user_name = user.full_name
    username = f"@{user.username}" if user.username else "Не указан"
    
    stats_text = (
        f"<b>📊 Ваша статистика</b>\n\n"
        f"<b>👤 Профиль:</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {user_name}\n"
        f"🔖 Username: {username}\n\n"
        f"<b>📈 Детальная статистика:</b>\n"
        "▪️ /game - Игровая статистика и прогресс\n"
        "▪️ /achievements - Ваши достижения и награды\n"
        "▪️ /leaderboard - Рейтинги игроков\n"
        "▪️ /invite - Рефералы и бонусы\n"
        "▪️ /calculator - Калькулятор доходности\n\n"
        f"Дата регистрации: {datetime.now().strftime('%d.%m.%Y')}"
    )
    
    await message.answer(stats_text, parse_mode=ParseMode.HTML)
    logger.info(f"User {user_id} requested /stats")