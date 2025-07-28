# ===============================================================
# Файл: bot/handlers/admin/__init__.py (НОВЫЙ ФАЙЛ)
# Описание: Делает папку 'admin' Python-пакетом и экспортирует
# все роутеры из этой директории для удобного импорта.
# ===============================================================

from .admin_menu import admin_router
from .moderation_handler import moderation_router
from .stats_handler import stats_router

__all__ = [
    "admin_router",
    "moderation_router",
    "stats_router",
]
