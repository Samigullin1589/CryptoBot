# ===============================================================
# Файл: bot/keyboards/mining_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Функции для создания инлайн-клавиатур для игры
# "Виртуальный Майнинг" и Калькулятора.
# ===============================================================
from typing import List, Set
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config.settings import settings
from bot.utils.models import AsicMiner

# --- Клавиатуры для "Виртуального Майнинга" ---

def get_mining_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает главное меню для игры 'Виртуальный Майнинг'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏪 Магазин оборудования", callback_data="game_nav:shop")
    builder.button(text="🖥️ Моя ферма и статистика", callback_data="game_nav:my_farm")
    builder.button(text="⚡️ Электроэнергия", callback_data="game_nav:electricity")
    builder.button(text="🤝 Пригласить друга", callback_data="game_action:invite")
    builder.button(text="💰 Вывод средств", callback_data="game_action:withdraw")
    builder.button(text="⬅️ Назад в главное меню", callback_data="nav:main_menu")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

# --- ИСПРАВЛЕНИЕ: Добавлена недостающая функция ---
def get_shop_keyboard(asics: List[AsicMiner], page: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для магазина с пагинацией."""
    builder = InlineKeyboardBuilder()
    items_per_page = settings.game.items_per_page
    start_index = page * items_per_page
    end_index = start_index + items_per_page

    for i, asic in enumerate(asics[start_index:end_index]):
        builder.button(
            text=f"▶️ {asic.name} (${asic.profitability:.2f}/день)",
            callback_data=f"game_action:start:{i + start_index}"
        )
    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"game_shop_page:{page - 1}"))
    if end_index < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"game_shop_page:{page + 1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ В меню майнинга", callback_data="nav:mining_game"))
    return builder.as_markup()
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

def get_my_farm_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для раздела 'Моя ферма'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню майнинга", callback_data="nav:mining_game")
    return builder.as_markup()

def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения вывода средств."""
    builder = InlineKeyboardBuilder()
    # Предполагаем, что URL партнера хранится в настройках
    partner_url = settings.game.partner_url
    if partner_url:
        builder.button(text="🎉 Получить у партнера", url=partner_url)
    builder.button(text="⬅️ В меню майнинга", callback_data="nav:mining_game")
    return builder.as_markup()

def get_electricity_menu_keyboard(current_tariff_name: str, unlocked_tariffs: Set[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру для управления тарифами на электроэнергию."""
    builder = InlineKeyboardBuilder()
    for name, details in settings.game.electricity_tariffs.items():
        if name in unlocked_tariffs:
            text = f"✅ {name}" if name == current_tariff_name else f"▶️ {name}"
            callback_data = f"game_tariff_select:{name}"
            builder.button(text=text, callback_data=callback_data)
        else:
            price = details['unlock_price']
            text = f"🔒 {name} (купить за {price:.0f} монет)"
            callback_data = f"game_tariff_buy:{name}"
            builder.button(text=text, callback_data=callback_data)
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ В меню майнинга", callback_data="nav:mining_game"))
    return builder.as_markup()

# --- Клавиатуры для Калькулятора ---

def get_calculator_cancel_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой отмены для калькулятора."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="calc_action:cancel")
    return builder.as_markup()

def get_currency_selection_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора валюты в калькуляторе."""
    builder = InlineKeyboardBuilder()
    builder.button(text="USD ($)", callback_data="calc_currency:usd")
    builder.button(text="RUB (₽)", callback_data="calc_currency:rub")
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="calc_action:cancel"))
    return builder.as_markup()

def get_asic_selection_keyboard(asics: List[AsicMiner], page: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора ASIC в калькуляторе с пагинацией."""
    builder = InlineKeyboardBuilder()
    items_per_page = 8
    start = page * items_per_page
    end = start + items_per_page

    for i, asic in enumerate(asics[start:end]):
        builder.button(text=f"✅ {asic.name}", callback_data=f"calc_select_asic:{i + start}")
    
    builder.adjust(2)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"calc_page:{page - 1}"))
    if end < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"calc_page:{page + 1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="calc_action:cancel"))
    return builder.as_markup()
