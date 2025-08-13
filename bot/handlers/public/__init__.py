# ===============================================================
# Файл: bot/handlers/public/__init__.py (ИСПРАВЛЕНО)
# Описание: Этот файл служит для обозначения директории как пакета Python
#           и для централизованного экспорта всех публичных роутеров.
# ===============================================================

from .menu_handlers import router as menu_router
from .price_handler import router as price_router
from .asic_handler import router as asic_router
from .news_handler import router as news_router
from .quiz_handler import router as quiz_router
from .market_info_handler import router as market_info_router
from .market_handler import router as market_router
from .crypto_center_handler import router as crypto_center_router
from .verification_public_handler import router as verification_public_router
from .achievements_handler import router as achievements_router
from .game_handler import router as game_handler
from .common_handler import router as common_router

__all__ = [
    "menu_router", "price_router", "asic_router", "news_handler",
    "quiz_router", "market_info_handler", "market_router",
    "crypto_center_router", "verification_public_router",
    "achievements_handler", "game_handler", "common_router"
]