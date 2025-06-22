import random
from typing import List
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config.settings import settings
from bot.utils.models import AsicMiner

PROMO_URL = "https://cutt.ly/5rWGcgYL"
PROMO_TEXTS = [
    "🎁 Суперцена на майнеры –50%", "🔥 Горячий прайс: скидка до 30%", "⏳ Лимитированная цена на ASIC – успей схватить!",
    "📉 Цена-провал: ASIC по демо-тарифу", "💎 VIP-прайс со скидкой 40%", "🚀 Обвал цен: ASIC от 70% MSRP",
    "🏷️ MEGA-Sale: ASIC по оптовой цене", "💣 Ценовой взрыв: скидка до 60%", "💥 Флеш-продажа: ASIC по цене прошлого года",
    "🚨 Срочно: прайс-ловушка – не пропусти!", "🕵️ Тайные скидки на ASIC внутри", "🎯 Меткий прайс: цены снижены на 35%",
    "🤑 ASIC по ценам Чёрной пятницы", "🔓 Узнай секретную цену – минус 45%", "🚪 Закрытая распродажа ASIC – вход по ссылке",
    "💌 Прайс-лист VIP с бонусом внутри", "🥷 Ниндзя-прайс: секретная скидка 40%", "🎉 Crazy Sale: ASIC по супер-ценам",
    "🌪️ Ценовой шторм: скидки до 55%", "⏰ Время скидок на ASIC истекает!", "💼 PRO-прайс для майнинг-профи",
    "🧨 Бомба-скидка: ASIC дешевле рынка", "🏃 Успей поймать выгодную цену!", "📅 Только сегодня: ASIC по спеццене",
    "🎲 ASIC-рулетка: цены упали на 50%", "🔐 Скрытая распродажа ASIC", "🎈 Лёгкий вход в майнинг: ASIC дешевле",
    "🥳 Праздничный прайс-шок на ASIC", "💹 Bull-прайс: мощные ASIC по выгодной цене"
]
ITEMS_PER_PAGE = 5

def get_promo_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=random.choice(PROMO_TEXTS), url=PROMO_URL)

def get_main_menu_keyboard():
    # ... (код этой функции без изменений)
    builder = InlineKeyboardBuilder()
    buttons = { "💹 Курс": "menu_price", "⚙️ Топ ASIC": "menu_asics", "⛏️ Калькулятор": "menu_calculator", "📰 Новости": "menu_news", "😱 Индекс Страха": "menu_fear_greed", "⏳ Халвинг": "menu_halving", "📡 Статус BTC": "menu_btc_status", "🧠 Викторина": "menu_quiz", "💎 Виртуальный Майнинг": "menu_mining" }
    for text, data in buttons.items():
        builder.button(text=text, callback_data=data)
    builder.adjust(2)
    builder.row(get_promo_button())
    return builder.as_markup()

def get_price_keyboard():
    # ... (код этой функции без изменений)
    builder = InlineKeyboardBuilder()
    for ticker in settings.popular_tickers:
        builder.button(text=ticker, callback_data=f"price_{ticker}")
    builder.adjust(len(settings.popular_tickers))
    builder.row(InlineKeyboardButton(text="➡️ Другая монета", callback_data="price_other"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu"))
    builder.row(get_promo_button())
    return builder.as_markup()

def get_quiz_keyboard():
    # ... (код этой функции без изменений)
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующий вопрос", callback_data="menu_quiz")
    builder.row(get_promo_button())
    return builder.as_markup()

def get_mining_menu_keyboard():
    # ... (код этой функции без изменений)
    builder = InlineKeyboardBuilder()
    builder.button(text="🏪 Магазин оборудования", callback_data="mining_shop")
    builder.button(text="🖥️ Моя ферма", callback_data="mining_my_farm")
    builder.button(text="⚡️ Электроэнергия", callback_data="mining_electricity")
    builder.button(text="📊 Статистика", callback_data="mining_stats")
    builder.button(text="💰 Вывод средств", callback_data="mining_withdraw")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_asic_shop_keyboard(asics: List[AsicMiner], page: int = 0):
    # ... (код этой функции без изменений)
    builder = InlineKeyboardBuilder()
    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    for i, asic in enumerate(asics[start_index:end_index]):
        builder.button(text=f"▶️ {asic.name} (${asic.profitability:.2f}/день)", callback_data=f"start_mining_{i + start_index}")
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"shop_page_{page - 1}"))
    if end_index < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"shop_page_{page + 1}"))
    builder.adjust(1)
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="⬅️ В меню майнинга", callback_data="menu_mining"))
    return builder.as_markup()

def get_my_farm_keyboard():
    # ... (код этой функции без изменений)
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню майнинга", callback_data="menu_mining")
    return builder.as_markup()

# --- НОВАЯ ФУНКЦИЯ ---
def get_withdraw_keyboard():
    """Создает клавиатуру для сообщения о выводе средств."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎉 Получить у партнера", url=PROMO_URL)
    builder.button(text="⬅️ В меню майнинга", callback_data="menu_mining")
    return builder.as_markup()