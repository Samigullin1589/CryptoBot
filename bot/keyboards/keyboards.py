import random
from typing import List, Dict, Any, Set
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем сервисы и настройки, которые нужны для новых клавиатур
from bot.services.crypto_center_service import CryptoCenterService
from bot.config.settings import settings
from bot.utils.models import AsicMiner

# --- ВАШ СУЩЕСТВУЮЩИЙ КОД (ОСТАВЛЕН БЕЗ ИЗМЕНЕНИЙ) ---

PROMO_URL = "https://cutt.ly/5rWGcgYL"
PROMO_TEXTS = [
    "🎁 Суперцена на майнеры –50%",
    "🔥 Горячий прайс: скидка до 30%",
    "⏳ Лимитированная цена на ASIC – успей схватить!",
    "📉 Цена-провал: ASIC по демо-тарифу",
    "💎 VIP-прайс со скидкой 40%",
    "🚀 Обвал цен: ASIC от 70% MSRP",
    "🏷️ MEGA-Sale: ASIC по оптовой цене",
    "💣 Ценовой взрыв: скидка до 60%",
    "💥 Флеш-продажа: ASIC по цене прошлого года",
    "🚨 Срочно: прайс-ловушка – не пропусти!",
    "🕵️ Тайные скидки на ASIC внутри",
    "🎯 Меткий прайс: цены снижены на 35%",
    "🤑 ASIC по ценам Чёрной пятницы",
    "🔓 Узнай секретную цену – минус 45%",
    "🚪 Закрытая распродажа ASIC – вход по ссылке",
    "💌 Прайс-лист VIP с бонусом внутри",
    "🥷 Ниндзя-прайс: секретная скидка 40%",
    "🎉 Crazy Sale: ASIC по супер-ценам",
    "🌪️ Ценовой шторм: скидки до 55%",
    "⏰ Время скидок на ASIC истекает!",
    "💼 PRO-прайс для майнинг-профи",
    "🧨 Бомба-скидка: ASIC дешевле рынка",
    "🏃 Успей поймать выгодную цену!",
    "📅 Только сегодня: ASIC по спеццене",
    "🎲 ASIC-рулетка: цены упали на 50%",
    "🔐 Скрытая распродажа ASIC",
    "🎈 Лёгкий вход в майнинг: ASIC дешевле",
    "🥳 Праздничный прайс-шок на ASIC",
    "💹 Bull-прайс: мощные ASIC по выгодной цене"
]
ITEMS_PER_PAGE = 5

def get_promo_button() -> InlineKeyboardButton:
    """Возвращает кнопку с рандомным промо-текстом."""
    return InlineKeyboardButton(text=random.choice(PROMO_TEXTS), url=PROMO_URL)

# --- ИЗМЕНЕНИЯ ВНЕСЕНЫ ТОЛЬКО ЗДЕСЬ ---

def get_main_menu_keyboard():
    """Создает главную клавиатуру меню."""
    builder = InlineKeyboardBuilder()
    buttons = {
        "💹 Курс": "menu_price", "⚙️ Топ ASIC": "menu_asics",
        "⛏️ Калькулятор": "menu_calculator", "📰 Новости": "menu_news",
        "😱 Индекс Страха": "menu_fear_greed", "⏳ Халвинг": "menu_halving",
        "📡 Статус BTC": "menu_btc_status", "🧠 Викторина": "menu_quiz",
        "💎 Виртуальный Майнинг": "menu_mining",
        # 👇 ДОБАВЛЕНА НОВАЯ КНОПКА
        "💎 Крипто-Центр": "menu_crypto_center"
    }
    for text, data in buttons.items():
        builder.button(text=text, callback_data=data)
    
    # Сохраняем вашу раскладку, добавив одну кнопку
    builder.adjust(2, 2, 2, 2, 2) 
    builder.row(get_promo_button())
    return builder.as_markup()

# --- ВАШ СУЩЕСТВУЮЩИЙ КОД (ОСТАВЛЕН БЕЗ ИЗМЕНЕНИЙ) ---

def get_price_keyboard():
    """Создает клавиатуру для выбора популярных монет."""
    builder = InlineKeyboardBuilder()
    for ticker in settings.popular_tickers:
        builder.button(text=ticker, callback_data=f"price_{ticker}")
    builder.adjust(len(settings.popular_tickers))
    builder.row(InlineKeyboardButton(text="➡️ Другая монета", callback_data="price_other"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu"))
    builder.row(get_promo_button())
    return builder.as_markup()

def get_quiz_keyboard():
    """
    Создает клавиатуру для викторины с возможностью выхода.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующий вопрос ➡️", callback_data="menu_quiz")
    builder.button(text="⬅️ Завершить", callback_data="back_to_main_menu")
    builder.adjust(2)
    builder.row(get_promo_button())
    return builder.as_markup()

def get_mining_menu_keyboard():
    """Создает клавиатуру для главного меню раздела 'Виртуальный Майнинг'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏪 Магазин оборудования", callback_data="mining_shop")
    builder.button(text="🖥️ Моя ферма", callback_data="mining_my_farm")
    builder.button(text="⚡️ Электроэнергия", callback_data="mining_electricity")
    builder.button(text="🤝 Пригласить друга", callback_data="mining_invite")
    builder.button(text="📊 Статистика", callback_data="mining_stats")
    builder.button(text="💰 Вывод средств", callback_data="mining_withdraw")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(2, 2, 2, 1)
    builder.row(get_promo_button())
    return builder.as_markup()

def get_asic_shop_keyboard(asics: List[AsicMiner], page: int = 0):
    """Создает клавиатуру для магазина ASIC с пагинацией."""
    builder = InlineKeyboardBuilder()
    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    for i, asic in enumerate(asics[start_index:end_index]):
        builder.button(
            text=f"▶️ {asic.name} (${asic.profitability:.2f}/день)",
            callback_data=f"start_mining_{i + start_index}"
        )
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"shop_page_{page - 1}"))
    if end_index < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"shop_page_{page + 1}"))
    builder.adjust(1)
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="⬅️ В меню майнинга", callback_data="menu_mining"))
    builder.row(get_promo_button())
    return builder.as_markup()

def get_my_farm_keyboard():
    """Создает клавиатуру для раздела 'Моя ферма'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню майнинга", callback_data="menu_mining")
    builder.row(get_promo_button())
    return builder.as_markup()

def get_withdraw_keyboard():
    """Создает клавиатуру для сообщения о выводе средств."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎉 Получить у партнера", url=PROMO_URL)
    builder.button(text="⬅️ В меню майнинга", callback_data="menu_mining")
    builder.row(get_promo_button())
    return builder.as_markup()

def get_electricity_menu_keyboard(current_tariff_name: str, unlocked_tariffs: Set[str]):
    """Создает клавиатуру для меню выбора тарифа на электроэнергию."""
    builder = InlineKeyboardBuilder()
    for name, details in settings.ELECTRICITY_TARIFFS.items():
        if name in unlocked_tariffs:
            text = f"✅ {name}" if name == current_tariff_name else f"▶️ {name}"
            callback_data = f"select_tariff_{name}"
            builder.button(text=text, callback_data=callback_data)
        else:
            price = details['unlock_price']
            text = f"🔒 {name} (купить за {price:.0f} монет)"
            callback_data = f"buy_tariff_{name}"
            builder.button(text=text, callback_data=callback_data)
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ В меню майнинга", callback_data="menu_mining"))
    builder.row(get_promo_button())
    return builder.as_markup()

def get_after_action_keyboard():
    """
    Клавиатура, отображаемая после выполнения действия (например, показа курса).
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.row(get_promo_button())
    return builder.as_markup()

# --- НОВЫЕ ФУНКЦИИ ДЛЯ КРИПТО-ЦЕНТРА ---

def get_crypto_center_main_menu_keyboard():
    """Создает клавиатуру для главного меню Крипто-Центра."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡️ Лента Новостей (Live)", callback_data="crypto_center_feed")
    builder.button(text="📚 Кураторские Гайды", callback_data="crypto_center_guides")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    builder.row(get_promo_button())
    return builder.as_markup()

def get_crypto_center_guides_menu_keyboard():
    """Создает клавиатуру для выбора типа кураторских гайдов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💧 Охота за Airdrop'ами", callback_data="guides_airdrops")
    builder.button(text="⛏️ Сигналы для майнеров", callback_data="guides_mining")
    builder.button(text="⬅️ Назад в Крипто-Центр", callback_data="back_to_crypto_center_main")
    builder.adjust(1)
    builder.row(get_promo_button())
    return builder.as_markup()

async def get_airdrops_list_keyboard(crypto_center_service: CryptoCenterService, redis_client: redis.Redis, user_id: int):
    """Создает клавиатуру со списком Airdrop-проектов и прогрессом пользователя."""
    builder = InlineKeyboardBuilder()
    airdrops = crypto_center_service.get_all_airdrops()
    
    for airdrop in airdrops:
        progress = await crypto_center_service.get_user_progress(user_id, airdrop['id'])
        total_tasks = len(airdrop['tasks'])
        progress_text = f"✅ {len(progress)}/{total_tasks}"
        
        builder.button(
            text=f"{airdrop['name']} ({progress_text})",
            callback_data=f"airdrop_details_{airdrop['id']}"
        )
    
    builder.button(text="⬅️ Назад к выбору гайдов", callback_data="crypto_center_guides")
    builder.adjust(1)
    builder.row(get_promo_button())
    return builder.as_markup()

async def get_airdrop_details_keyboard(airdrop: Dict[str, Any], user_progress: List[int]):
    """Создает клавиатуру с чеклистом задач для конкретного Airdrop."""
    builder = InlineKeyboardBuilder()
    
    for i, task_text in enumerate(airdrop['tasks']):
        status_emoji = "✅" if i in user_progress else "☑️"
        builder.button(
            text=f"{status_emoji} {task_text}",
            callback_data=f"toggle_task_{airdrop['id']}_{i}"
        )
        
    if airdrop.get('guide_url'):
        builder.button(text="🔗 Подробный гайд", url=airdrop['guide_url'])
        
    builder.button(text="⬅️ Назад к списку", callback_data="back_to_airdrops_list")
    builder.adjust(1)
    builder.row(get_promo_button())
    return builder.as_markup()
