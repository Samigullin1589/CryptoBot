# ===============================================================
# Файл: bot/keyboards/mining_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Функции для создания всех инлайн-клавиатур,
# связанных с игрой "Виртуальный Майнинг" и Калькулятором.
# ===============================================================
import re
from typing import List, Dict, Set
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.models import AsicMiner
from bot.config.settings import settings

# --- Клавиатуры для Игры ---

def get_mining_menu_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏪 Магазин оборудования", callback_data="game_nav:shop:0")
    builder.button(text="🖥️ Моя ферма", callback_data="game_nav:farm")
    builder.button(text="📊 Моя статистика", callback_data="game_nav:stats")
    builder.button(text="⚡️ Электроэнергия", callback_data="game_nav:electricity")
    builder.button(text="🤝 Пригласить друга", callback_data="game_nav:invite")
    builder.button(text="💰 Вывод средств", callback_data="game_nav:withdraw")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(2, 2, 2, 1)
    return builder

def get_asic_shop_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    items_per_page = 8
    start, end = page * items_per_page, (page + 1) * items_per_page
    
    for i, asic in enumerate(asics[start:end]):
        builder.button(text=f"{asic.name}", callback_data=f"game_action:start_mining:{start + i}")
    
    builder.adjust(2)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"game_nav:shop:{page - 1}"))
    if end < len(asics):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"game_nav:shop:{page + 1}"))
    
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню игры", callback_data="game_nav:main_menu"))
    return builder

def get_my_farm_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="game_nav:farm")
    builder.button(text="⬅️ Назад в меню игры", callback_data="game_nav:main_menu")
    builder.adjust(1)
    return builder

def get_electricity_menu_keyboard(current_tariff: str, unlocked_tariffs: Set[str]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for name, info in settings.game.ELECTRICITY_TARIFFS.items():
        if name in unlocked_tariffs:
            text = f"✅ {name}" if name == current_tariff else f"▶️ {name}"
            callback = f"game_action:select_tariff:{name}"
        else:
            text = f"🔒 {name} ({info['unlock_price']} монет)"
            callback = f"game_action:buy_tariff:{name}"
        builder.button(text=text, callback_data=callback)
    
    builder.button(text="⬅️ Назад в меню игры", callback_data="game_nav:main_menu")
    builder.adjust(1)
    return builder

def get_withdraw_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    # TODO: Заменить URL на актуальный URL партнера
    builder.button(text="🎁 Получить скидку у партнера", url="https://t.me/mining_sale_admin")
    builder.button(text="⬅️ Назад в меню игры", callback_data="game_nav:main_menu")
    builder.adjust(1)
    return builder

# --- Клавиатуры для Калькулятора ---

def get_calculator_cancel_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="calc_action:cancel")
    return builder

def get_calculator_currency_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="USD ($)", callback_data="calc_action:set_currency:usd")
    builder.button(text="RUB (₽)", callback_data="calc_action:set_currency:rub")
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="calc_action:cancel"))
    return builder

def get_calculator_asic_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    items_per_page = 8
    start, end = page * items_per_page, (page + 1) * items_per_page

    for i, asic in enumerate(asics[start:end]):
        is_valid = all([
            asic.power and asic.power > 0,
            asic.algorithm and asic.algorithm != "Unknown",
            asic.hashrate and asic.hashrate.lower() != 'n/a' and re.search(r'[\d.]+', asic.hashrate)
        ])
        if is_valid:
            builder.button(text=f"✅ {asic.name}", callback_data=f"calc_action:select_asic:{start + i}")
        else:
            builder.button(text=f"🚫 {asic.name}", callback_data="calc_action:invalid_asic")
            
    builder.adjust(2)
    nav_buttons = []
    total_pages = (len(asics) + items_per_page - 1) // items_per_page
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"calc_nav:page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"calc_nav:page:{page + 1}"))
    
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="calc_action:cancel"))
    return builder
