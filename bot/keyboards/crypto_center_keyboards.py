# =================================================================================
# Файл: bot/keyboards/crypto_center_keyboards.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ГОТОВАЯ)
# Описание: Генерация интерактивных клавиатур для Крипто-Центра.
# =================================================================================

from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.models import AirdropProject, NewsArticle

# Главный префикс для всех callback-данных, чтобы избежать конфликтов
CC_CALLBACK_PREFIX = "cc" # Crypto Center

def get_crypto_center_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает главное меню Крипто-Центра."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💎 Airdrop Alpha (Персонально)", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:0"))
    builder.row(InlineKeyboardButton(text="⚙️ Mining Alpha (Персонально)", callback_data=f"{CC_CALLBACK_PREFIX}:mining:list:0"))
    builder.row(InlineKeyboardButton(text="📰 Live Лента Новостей", callback_data=f"{CC_CALLBACK_PREFIX}:news:list:0"))
    return builder.as_markup()

def get_airdrop_list_keyboard(projects: List[AirdropProject], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком Airdrop-проектов и постраничной навигацией."""
    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.row(InlineKeyboardButton(text=f"{project.name} ({project.status})", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:view:{project.id}"))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="do_nothing"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:{page + 1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data=f"{CC_CALLBACK_PREFIX}:main"))
    return builder.as_markup()

def get_airdrop_details_keyboard(project: AirdropProject, completed_tasks: List[int]) -> InlineKeyboardMarkup:
    """
    Создает интерактивную клавиатуру для конкретного Airdrop-проекта с чек-листом задач.
    """
    builder = InlineKeyboardBuilder()
    
    for i, task in enumerate(project.tasks):
        status_icon = "✅" if i in completed_tasks else "☑️"
        button_text = f"{status_icon} {task}"
        callback_data = f"{CC_CALLBACK_PREFIX}:airdrops:task:{project.id}:{i}"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=callback_data))

    if project.guide_url:
        builder.row(InlineKeyboardButton(text="🔗 Открыть гайд", url=project.guide_url))
        
    builder.row(InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"{CC_CALLBACK_PREFIX}:airdrops:list:0"))
    return builder.as_markup()

def get_mining_alpha_keyboard(signals: List[Dict[str, Any]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для отображения майнинг-сигналов."""
    builder = InlineKeyboardBuilder()
    for signal in signals:
        builder.row(InlineKeyboardButton(text=f"{signal['name']} ({signal['algorithm']})", callback_data=f"{CC_CALLBACK_PREFIX}:mining:view:{signal['id']}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{CC_CALLBACK_PREFIX}:mining:list:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="do_nothing"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{CC_CALLBACK_PREFIX}:mining:list:{page + 1}"))
        
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data=f"{CC_CALLBACK_PREFIX}:main"))
    return builder.as_markup()

def get_news_feed_keyboard(articles: List[NewsArticle], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для новостной ленты."""
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Предыдущие", callback_data=f"{CC_CALLBACK_PREFIX}:news:list:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Следующие ▶️", callback_data=f"{CC_CALLBACK_PREFIX}:news:list:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data=f"{CC_CALLBACK_PREFIX}:main"))
    return builder.as_markup()