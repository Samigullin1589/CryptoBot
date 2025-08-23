# =================================================================================
# Файл: bot/keyboards/keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025, С ФАБРИКАМИ)
# Описание: Основной модуль для самых общих клавиатур.
# ИСПРАВЛЕНИЕ: Полный переход на использование CallbackData фабрик с методом .pack().
# =================================================================================
import random
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from .callback_factories import MenuCallback

def get_promo_button() -> InlineKeyboardButton:
    """Создает универсальную промо-кнопку со случайным текстом."""
    promo_url = "https://example.com" # Замените на реальную ссылку
    promo_texts = [
        "🎁 Суперцена на майнеры –50%", "🔥 Горячий прайс: скидка до 30%",
        "⏳ Лимитированная цена на ASIC!", "📉 Цена-провал: ASIC по демо-тарифу",
        "💎 VIP-прайс со скидкой 40%", "🚀 Обвал цен: ASIC от 70% MSRP"
    ]
    return InlineKeyboardButton(text=random.choice(promo_texts), url=promo_url)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню с использованием фабрики MenuCallback."""
    builder = InlineKeyboardBuilder()
    
    buttons = {
        "💹 Курс": "price", "⚙️ Топ ASIC": "asics",
        "⛏️ Калькулятор": "calculator", "📰 Новости": "news",
        "😱 Индекс Страха": "fear_index", "⏳ Халвинг": "halving",
        "📡 Статус BTC": "btc_status", "🧠 Викторина": "quiz",
        "💎 Виртуальный Майнинг": "game", "💎 Крипто-Центр": "crypto_center"
    }
    for text, action in buttons.items():
        builder.button(
            text=text, 
            callback_data=MenuCallback(level=0, action=action).pack()
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