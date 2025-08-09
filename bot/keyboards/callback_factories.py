# =================================================================================
# Файл: bot/keyboards/callback_factories.py (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)
# Описание: Централизованное определение всех структур данных для инлайн-кнопок.
# ИСПРАВЛЕНИЕ: Добавлена недостающая фабрика `NewsCallback` для устранения ImportError.
# =================================================================================

from aiogram.filters.callback_data import CallbackData

class MenuCallback(CallbackData, prefix="menu"):
    """
    Фабрика для навигации по главному меню.
    - level: уровень меню (0 - главное)
    - action: конкретное действие (например, 'price', 'news')
    """
    level: int
    action: str

class PriceCallback(CallbackData, prefix="price"):
    """
    Фабрика для действий в разделе курсов.
    - action: действие ('show', 'search')
    - coin_id: идентификатор монеты (например, 'bitcoin')
    """
    action: str
    coin_id: str | None = None

class NewsCallback(CallbackData, prefix="news"):
    """
    Фабрика для навигации в разделе новостей.
    - action: действие ('list_sources', 'get_feed')
    - source_key: ключ источника (например, 'forklog')
    """
    action: str
    source_key: str | None = None

class PaginatorCallback(CallbackData, prefix="paginator"):
    """
    Универсальная фабрика для любой пагинации.
    - action: для какого раздела пагинация (например, 'asics', 'news_feed')
    - page: номер страницы
    """
    action: str
    page: int
