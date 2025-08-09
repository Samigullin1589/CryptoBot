# =================================================================================
# Файл: bot/keyboards/callback_factories.py (НОВЫЙ ФАЙЛ, ПРОМЫШЛЕННЫЙ СТАНДАРТ)
# Описание: Централизованное определение всех структур данных для инлайн-кнопок.
# Этот файл является "единым источником правды" для всех колбэков в боте.
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
    coin_id: str | None = None # coin_id не обязателен для кнопки "поиск"

class PaginatorCallback(CallbackData, prefix="paginator"):
    """
    Универсальная фабрика для любой пагинации.
    - action: для какого раздела пагинация (например, 'asics', 'news_feed')
    - page: номер страницы
    """
    action: str
    page: int
