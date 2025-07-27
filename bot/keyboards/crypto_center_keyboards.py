# ===============================================================
# Файл: bot/keyboards/crypto_center_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Функции для создания инлайн-клавиатур для
# всех разделов Крипто-Центра.
# ===============================================================
from typing import List, Dict, Set
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_crypto_center_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню Крипто-Центра."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡️ Лента новостей (AI-Анализ)", callback_data="cc_nav:feed")
    builder.button(text="🤖 Аналитика и Гайды от AI", callback_data="cc_nav:guides_menu")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_crypto_center_guides_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для меню выбора гайдов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💧 Охота за Airdrop'ами", callback_data="cc_nav:airdrops_list:1")
    builder.button(text="⛏️ Сигналы для майнеров", callback_data="cc_nav:mining_signals")
    builder.button(text="⬅️ Назад в Крипто-Центр", callback_data="cc_nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_back_to_cc_menu_keyboard(level: str = "main_menu") -> InlineKeyboardMarkup:
    """Создает клавиатуру для возврата в меню Крипто-Центра."""
    builder = InlineKeyboardBuilder()
    if level == "guides_menu":
        builder.button(text="⬅️ Назад к выбору аналитики", callback_data="cc_nav:guides_menu")
    else:
        builder.button(text="⬅️ Назад в Крипто-Центр", callback_data="cc_nav:main_menu")
    return builder.as_markup()

def get_live_feed_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для ленты новостей."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить и проанализировать", callback_data="cc_nav:feed")
    builder.button(text="⬅️ Назад в Крипто-Центр", callback_data="cc_nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_airdrops_list_keyboard(airdrops_on_page: List[Dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для списка Airdrop'ов с пагинацией."""
    builder = InlineKeyboardBuilder()
    for airdrop in airdrops_on_page:
        builder.button(
            text=f"{airdrop['name']} ({airdrop['progress_text']})",
            callback_data=f"cc_action:show_airdrop:{airdrop['id']}"
        )
    
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        builder.button(text="◀️", callback_data=f"cc_nav:airdrops_list:{prev_page}")
        builder.button(text=f"{page}/{total_pages}", callback_data="do_nothing")
        builder.button(text="▶️", callback_data=f"cc_nav:airdrops_list:{next_page}")

    builder.button(text="⬅️ Назад к выбору аналитики", callback_data="cc_nav:guides_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_airdrop_details_keyboard(airdrop: Dict, user_progress: Set[int]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с чеклистом для конкретного Airdrop'а."""
    builder = InlineKeyboardBuilder()
    airdrop_id = airdrop.get('id')
    for i, task in enumerate(airdrop.get('tasks', [])):
        status_emoji = "✅" if i in user_progress else "☑️"
        builder.button(
            text=f"{status_emoji} {task['name']}",
            callback_data=f"cc_action:toggle_task:{airdrop_id}:{i}"
        )
    builder.button(text="⬅️ Назад к списку Airdrop'ов", callback_data="cc_nav:airdrops_list:1")
    builder.adjust(1)
    return builder.as_markup()
