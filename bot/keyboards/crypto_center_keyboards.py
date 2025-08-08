# =================================================================================
# Файл: bot/keyboards/crypto_center_keyboards.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Клавиатуры для раздела "Крипто-Центр".
# =================================================================================
from typing import List
from math import ceil
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.utils.models import AirdropProject, NewsArticle

CC_CALLBACK_PREFIX = "cc"
PAGE_SIZE = 5

def get_crypto_center_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает главное меню Крипто-Центра."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Airdrop Alpha", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:0")
    builder.button(text="⚙️ Mining Alpha", callback_data=f"{CC_CALLBACK_PREFIX}:mining:list:0")
    builder.button(text="📰 Live Лента", callback_data=f"{CC_CALLBACK_PREFIX}:news:list:0")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_airdrop_list_keyboard(projects: List[AirdropProject], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для списка Airdrop-проектов с пагинацией."""
    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(text=f"🔹 {project.name}", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:view:{project.id}")
    builder.adjust(1)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(builder.button(text="⬅️", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(builder.button(text="➡️", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(builder.button(text="⬅️ Назад в Крипто-Центр", callback_data=f"{CC_CALLBACK_PREFIX}:main"))
    return builder.as_markup()

def get_airdrop_details_keyboard(project: AirdropProject, completed_tasks: List[int]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с чек-листом задач для Airdrop-проекта."""
    builder = InlineKeyboardBuilder()
    for i, task in enumerate(project.tasks):
        status_emoji = "✅" if i in completed_tasks else "☑️"
        builder.button(text=f"{status_emoji} {task}", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:task:{project.id}:{i}")
    builder.adjust(1)
    if project.guide_url:
        builder.row(builder.button(text="🔗 Открыть гайд", url=project.guide_url))
    builder.row(builder.button(text="⬅️ Назад к списку", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:0"))
    return builder.as_markup()

def get_mining_alpha_keyboard(signals: List[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для списка майнинг-сигналов."""
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(builder.button(text="⬅️", callback_data=f"{CC_CALLBACK_PREFIX}:mining:list:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(builder.button(text="➡️", callback_data=f"{CC_CALLBACK_PREFIX}:mining:list:{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(builder.button(text="⬅️ Назад в Крипто-Центр", callback_data=f"{CC_CALLBACK_PREFIX}:main"))
    return builder.as_markup()

def get_news_feed_keyboard(articles: List[NewsArticle], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для новостной ленты."""
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(builder.button(text="⬅️", callback_data=f"{CC_CALLBACK_PREFIX}:news:list:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(builder.button(text="➡️", callback_data=f"{CC_CALLBACK_PREFIX}:news:list:{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(builder.button(text="⬅️ Назад в Крипто-Центр", callback_data=f"{CC_CALLBACK_PREFIX}:main"))
    return builder.as_markup()
