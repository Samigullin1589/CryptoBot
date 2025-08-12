# ===============================================================
# Файл: bot/handlers/public/__init__.py (НОВЫЙ / ИСПРАВЛЕНО)
# Описание: Экспортирует все публичные роутеры для
#           централизованной регистрации.
# ===============================================================

from .achievements_handler import router as achievements_router
from .asic_handler import router as asic_router
from .common_handler import router as common_router
from .crypto_center_handler import router as crypto_center_router
from .game_handler import router as game_router
from .market_data_handler import router as market_data_router
from .market_handler import router as market_router
from .menu_handlers import router as menu_router
from .news_handler import router as news_router
from .price_handler import router as price_router
from .quiz_handler import router as quiz_router
from .verification_public_handler import router as verification_public_router

__all__ = [
    "achievements_router",
    "asic_router",
    "common_router",
    "crypto_center_router",
    "game_router",
    "market_data_router",
    "market_router",
    "menu_router",
    "news_router",
    "price_router",
    "quiz_router",
    "verification_public_router",
]