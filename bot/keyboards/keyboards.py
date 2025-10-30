# src/bot/keyboards/keyboards.py
import random
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from .callback_factories import MenuCallback, PriceCallback

def get_promo_button() -> InlineKeyboardButton:
    """Создает универсальную промо-кнопку со случайным текстом."""
    promo_url = "https://example.com"
    promo_texts = [
        "🎁 Суперцена на майнеры –50%", "🔥 Горячий прайс: скидка до 30%",
        "⏳ Лимитированная цена на ASIC!", "📉 Цена-провал: ASIC по демо-тарифу",
        "💎 VIP-прайс со скидкой 40%", "🚀 Обвал цен: ASIC от 70% MSRP"
    ]
    return InlineKeyboardButton(text=random.choice(promo_texts), url=promo_url)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню с использованием фабрики."""
    builder = InlineKeyboardBuilder()
    
    # ИСПРАВЛЕНО: Кнопка "Курс" теперь использует PriceCallback
    builder.button(
        text="💹 Курс", 
        callback_data=PriceCallback(action="open", coin_id="").pack()
    )
    builder.button(
        text="⚙️ Топ ASIC", 
        callback_data=MenuCallback(level=0, action="asics").pack()
    )
    builder.button(
        text="⛏️ Калькулятор", 
        callback_data=MenuCallback(level=0, action="calculator").pack()
    )
    builder.button(
        text="📰 Новости", 
        callback_data=MenuCallback(level=0, action="news").pack()
    )
    builder.button(
        text="😱 Индекс Страха", 
        callback_data=MenuCallback(level=0, action="fear_index").pack()
    )
    builder.button(
        text="⏳ Халвинг", 
        callback_data=MenuCallback(level=0, action="halving").pack()
    )
    builder.button(
        text="📡 Статус BTC", 
        callback_data=MenuCallback(level=0, action="btc_status").pack()
    )
    builder.button(
        text="🧠 Викторина", 
        callback_data=MenuCallback(level=0, action="quiz").pack()
    )
    builder.button(
        text="💎 Виртуальный Майнинг", 
        callback_data=MenuCallback(level=0, action="game").pack()
    )
    builder.button(
        text="💎 Крипто-Центр", 
        callback_data=MenuCallback(level=0, action="crypto_center").pack()
    )
        
    builder.adjust(2)
    builder.row(get_promo_button())
    return builder.as_markup()

def get_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает универсальную клавиатуру с кнопкой 'Назад в главное меню',
    используя фабрику MenuCallback.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад в главное меню", 
        callback_data=MenuCallback(level=0, action="main").pack()
    )
    builder.row(get_promo_button())
    return builder.as_markup()