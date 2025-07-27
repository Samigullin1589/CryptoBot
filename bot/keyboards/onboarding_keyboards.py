# ===============================================================
# Файл: bot/keyboards/onboarding_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Функции для создания инлайн-клавиатур, используемых
# в процессе знакомства нового пользователя с ботом.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_onboarding_start_keyboard() -> InlineKeyboardMarkup:
    """Создает стартовую клавиатуру для онбординга."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Начать знакомство", callback_data="onboarding:step_1")
    builder.button(text="Пропустить", callback_data="onboarding:skip")
    builder.adjust(1)
    return builder.as_markup()

def get_onboarding_step_keyboard(step: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для конкретного шага онбординга.
    
    :param step: Номер текущего шага.
    """
    builder = InlineKeyboardBuilder()
    if step == 1:
        # callback_data соответствует тому, что ожидает price_handler
        builder.button(text="💹 Попробовать: Узнать курс BTC", callback_data="price:BTC")
        builder.button(text="Далее ➡️", callback_data="onboarding:step_2")
    elif step == 2:
        # callback_data соответствует тому, что ожидает asic_handler
        builder.button(text="⚙️ Попробовать: Показать Топ ASIC", callback_data="top_asics:page:0:profitability")
        builder.button(text="Далее ➡️", callback_data="onboarding:step_3")
    elif step == 3:
        # callback_data соответствует тому, что ожидает crypto_center_handler
        builder.button(text="💎 Попробовать: Войти в Крипто-Центр", callback_data="cc_nav:main")
        builder.button(text="✅ Все понятно!", callback_data="onboarding:finish")
    
    builder.adjust(1)
    return builder.as_markup()
