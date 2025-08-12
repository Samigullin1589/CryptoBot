# ===============================================================
# Файл: bot/handlers/admin/__init__.py (ОКОНЧАТЕЛЬНО ИСПРАВЛЕНО)
# Описание: Экспортирует все роутеры из директории admin для
#           централизованной регистрации в главном приложении.
# ===============================================================

from .admin_menu import admin_router
from .moderation_handler import moderation_router
from .stats_handler import stats_router
from .verification_admin_handler import router as verification_admin_router
from .game_admin_handler import router as game_admin_router

__all__ = [
    "admin_router",
    "moderation_router",
    "stats_router",
    "verification_admin_router",
    "game_admin_router",
]