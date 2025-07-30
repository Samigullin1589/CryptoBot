# ===============================================================
# Файл: bot/keyboards/crypto_center_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Клавиатуры для Крипто-Центра с использованием CallbackData.
# ===============================================================
from typing import List, Dict, Any
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData

# --- Фабрики CallbackData ---

class AirdropListPage(CallbackData, prefix="cc_air_page"):
    page: int

class AirdropDetails(CallbackData, prefix="cc_air_details"):
    airdrop_id: str

class AirdropTask(CallbackData, prefix="cc_air_task"):
    airdrop_id: str
    task_index: int

# --- Генераторы клавиатур ---

def get_crypto_center_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Гайды и Возможности", callback_data="cc_nav:guides_menu")
    builder.button(text="📰 Лента с AI-анализом", callback_data="cc_nav:feed")
    builder.button(text="⬅️ Главное меню", callback_data="nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_crypto_center_guides_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🪂 Потенциальные Airdrop'ы", callback_data=AirdropListPage(page=1).pack())
    builder.button(text="⛏️ Майнинг-сигналы", callback_data="cc_nav:mining_signals")
    builder.button(text="⬅️ Назад в Крипто-Центр", callback_data="cc_nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_back_to_cc_menu_keyboard(menu: str = 'main_menu') -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=f"cc_nav:{menu}")
    return builder.as_markup()

def get_live_feed_keyboard() -> InlineKeyboardMarkup:
    return get_back_to_cc_menu_keyboard('main_menu')

def get_airdrops_list_keyboard(airdrops: List[Dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for airdrop in airdrops:
        builder.button(text=f"{airdrop['name']} ({airdrop['status']})", callback_data=AirdropDetails(airdrop_id=airdrop['id']).pack())
    
    nav_row = []
    if page > 1:
        nav_row.append(builder.button(text="⬅️", callback_data=AirdropListPage(page=page - 1).pack()))
    if page < total_pages:
        nav_row.append(builder.button(text="➡️", callback_data=AirdropListPage(page=page + 1).pack()))
        
    builder.row(*nav_row)
    builder.button(text="⬅️ Назад к гайдам", callback_data="cc_nav:guides_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_airdrop_details_keyboard(airdrop: Dict, user_progress: List[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, task in enumerate(airdrop.get('tasks', [])):
        status_icon = "✅" if i in user_progress else "☑️"
        builder.button(
            text=f"{status_icon} {task}",
            callback_data=AirdropTask(airdrop_id=airdrop['id'], task_index=i).pack()
        )
    if airdrop.get('guide_url'):
        builder.button(text="🔗 Открыть полный гайд", url=airdrop['guide_url'])
        
    builder.button(text="⬅️ Назад к списку", callback_data=AirdropListPage(page=1).pack())
    builder.adjust(1)
    return builder.as_markup()
