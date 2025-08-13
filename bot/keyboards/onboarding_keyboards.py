# ===============================================================
# Файл: bot/keyboards/onboarding_keyboards.py
# Описание: Функции для создания инлайн-клавиатур, используемых
# в процессе знакомства нового пользователя с ботом.
# ИСПРАВЛЕНИЕ: Переход на использование фабрик CallbackData.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from .callback_factories import OnboardingCallback, PriceCallback, AsicCallback, CryptoCenterCallback

def get_onboarding_start_keyboard() -> InlineKeyboardMarkup:
    """Создает стартовую клавиатуру для онбординга."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Начать знакомство", callback_data=OnboardingCallback(action="step_1").pack())
    builder.button(text="Пропустить", callback_data=OnboardingCallback(action="skip").pack())
    builder.adjust(1)
    return builder.as_markup()

def get_onboarding_step_keyboard(step: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для конкретного шага онбординга.
    
    :param step: Номер текущего шага.
    """
    builder = InlineKeyboardBuilder()
    if step == 1:
        builder.button(text="💹 Попробовать: Узнать курс BTC", callback_data=PriceCallback(action="show", coin_id="bitcoin").pack())
        builder.button(text="Далее ➡️", callback_data=OnboardingCallback(action="step_2").pack())
    elif step == 2:
        builder.button(text="⚙️ Попробовать: Показать Топ ASIC", callback_data=AsicCallback(action="page", page=1).pack())
        builder.button(text="Далее ➡️", callback_data=OnboardingCallback(action="step_3").pack())
    elif step == 3:
        builder.button(text="💎 Попробовать: Войти в Крипто-Центр", callback_data=CryptoCenterCallback(action="main").pack())
        builder.button(text="✅ Все понятно!", callback_data=OnboardingCallback(action="finish").pack())
    
    builder.adjust(1)
    return builder.as_markup()