# ===============================================================
# Файл: bot/keyboards/keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Основной модуль для самых общих клавиатур.
# Содержит главное меню и универсальные кнопки.
# ===============================================================
import random
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import settings # Предполагаем, что промо-данные в настройках

def get_promo_button() -> InlineKeyboardButton:
    """Создает универсальную промо-кнопку со случайным текстом."""
    # В идеале, эти данные должны быть в settings.py
    promo_url = "https://cutt.ly/5rWGcgYL"
    promo_texts = [
        "🎁 Суперцена на майнеры –50%", "🔥 Горячий прайс: скидка до 30%",
        "⏳ Лимитированная цена на ASIC!", "📉 Цена-провал: ASIC по демо-тарифу",
        "💎 VIP-прайс со скидкой 40%", "🚀 Обвал цен: ASIC от 70% MSRP"
    ]
    return InlineKeyboardButton(text=random.choice(promo_texts), url=promo_url)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()
    # Используем структурированные callback'и `nav:<destination>`
    buttons = {
        "💹 Курс": "nav:price", "⚙️ Топ ASIC": "nav:asics",
        "⛏️ Калькулятор": "nav:calculator", "📰 Новости": "nav:news",
        "😱 Индекс Страха": "nav:market_fear_greed", "⏳ Халвинг": "nav:market_halving",
        "📡 Статус BTC": "nav:market_btc_status", "🧠 Викторина": "nav:quiz",
        "💎 Виртуальный Майнинг": "nav:mining_game",
        "💎 Крипто-Центр": "nav:crypto_center"
    }
    for text, data in buttons.items():
        builder.button(text=text, callback_data=data)
        
    builder.adjust(2) # Все кнопки по 2 в ряд
    builder.row(get_promo_button())
    return builder.as_markup()

def get_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает универсальную клавиатуру с кнопкой 'Назад в главное меню'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.row(get_promo_button())
    return builder.as_markup()
