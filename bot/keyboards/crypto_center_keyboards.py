# =================================================================================
# Файл: bot/keyboards/crypto_center_keyboards.py (ВЕРСИЯ "Distinguished Engineer")
# Описание: Клавиатуры для раздела "Крипто-Центр".
# ИСПРАВЛЕНИЕ: Переход на использование фабрик CallbackData.
# =================================================================================
from typing import List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.models import AirdropProject, NewsArticle
from .callback_factories import CryptoCenterCallback, MenuCallback

PAGE_SIZE = 5

def get_crypto_center_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает главное меню Крипто-Центра."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Airdrop Alpha", callback_data=CryptoCenterCallback(action="airdrops_list", page=0).pack())
    builder.button(text="⚙️ Mining Alpha", callback_data=CryptoCenterCallback(action="mining_list", page=0).pack())
    builder.button(text="📰 Live Лента", callback_data=CryptoCenterCallback(action="news_list", page=0).pack())
    builder.button(text="🏠 Главное меню", callback_data=MenuCallback(level=0, action="main").pack())
    builder.adjust(1)
    return builder.as_markup()

def get_airdrop_list_keyboard(projects: List[AirdropProject], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для списка Airdrop-проектов с пагинацией."""
    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(text=f"🔹 {project.name}", callback_data=CryptoCenterCallback(action="airdrop_view", project_id=project.id).pack())
    builder.adjust(1)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=CryptoCenterCallback(action="airdrops_list", page=page - 1).pack()))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=CryptoCenterCallback(action="airdrops_list", page=page + 1).pack()))
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Крипто-Центр", callback_data=CryptoCenterCallback(action="main").pack()))
    return builder.as_markup()

def get_airdrop_details_keyboard(project: AirdropProject, completed_tasks: List[int]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с чек-листом задач для Airdrop-проекта."""
    builder = InlineKeyboardBuilder()
    for i, task in enumerate(project.tasks):
        status_emoji = "✅" if i in completed_tasks else "☑️"
        builder.button(text=f"{status_emoji} {task}", callback_data=CryptoCenterCallback(action="airdrop_task", project_id=project.id, task_index=i).pack())
    builder.adjust(1)
    if project.guide_url:
        builder.row(InlineKeyboardButton(text="🔗 Открыть гайд", url=project.guide_url))
    builder.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=CryptoCenterCallback(action="airdrops_list", page=0).pack()))
    return builder.as_markup()

def get_mining_alpha_keyboard(signals: List[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для списка майнинг-сигналов."""
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=CryptoCenterCallback(action="mining_list", page=page - 1).pack()))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=CryptoCenterCallback(action="mining_list", page=page + 1).pack()))
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Крипто-Центр", callback_data=CryptoCenterCallback(action="main").pack()))
    return builder.as_markup()

def get_news_feed_keyboard(articles: List[NewsArticle], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для новостной ленты."""
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=CryptoCenterCallback(action="news_list", page=page - 1).pack()))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=CryptoCenterCallback(action="news_list", page=page + 1).pack()))
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Крипто-Центр", callback_data=CryptoCenterCallback(action="main").pack()))
    return builder.as_markup()