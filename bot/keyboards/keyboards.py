import random
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config.settings import settings

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

def get_promo_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=random.choice(PROMO_TEXTS), url=PROMO_URL)

def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = {
        "💹 Курс": "menu_price", "⚙️ Топ ASIC": "menu_asics",
        "⛏️ Калькулятор": "menu_calculator", "📰 Новости": "menu_news",
        "😱 Индекс Страха": "menu_fear_greed", "⏳ Халвинг": "menu_halving",
        "📡 Статус BTC": "menu_btc_status", "🧠 Викторина": "menu_quiz",
        "💎 Виртуальный Майнинг": "menu_mining"
    }
    for text, data in buttons.items():
        builder.button(text=text, callback_data=data)
    builder.adjust(2)
    builder.row(get_promo_button())
    return builder.as_markup()

def get_price_keyboard():
    builder = InlineKeyboardBuilder()
    for ticker in settings.popular_tickers:
        builder.button(text=ticker, callback_data=f"price_{ticker}")
    builder.adjust(len(settings.popular_tickers))
    builder.row(InlineKeyboardButton(text="➡️ Другая монета", callback_data="price_other"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu"))
    builder.row(get_promo_button())
    return builder.as_markup()

def get_quiz_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующий вопрос", callback_data="menu_quiz")
    builder.row(get_promo_button())
    return builder.as_markup()

# --- НОВАЯ ФУНКЦИЯ ДЛЯ МЕНЮ МАЙНИНГА ---
def get_mining_menu_keyboard():
    """
    Создает клавиатуру для главного меню раздела "Виртуальный Майнинг".
    """
    builder = InlineKeyboardBuilder()
    # Кнопки согласно нашему ТЗ v2.0
    builder.button(text="🏪 Магазин оборудования", callback_data="mining_shop")
    builder.button(text="🖥️ Моя ферма", callback_data="mining_my_farm")
    builder.button(text="⚡️ Электроэнергия", callback_data="mining_electricity")
    builder.button(text="📊 Статистика", callback_data="mining_stats")
    builder.button(text="💰 Вывод средств", callback_data="mining_withdraw")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    
    # Расставляем кнопки в ряды для красоты
    builder.adjust(2, 2, 1, 1)
    
    return builder.as_markup()