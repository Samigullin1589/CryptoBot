# =============================================================================
# Файл: src/bot/handlers/public/__init__.py (ИСПРАВЛЕННЫЙ)
# Описание: Исправлена логика агрегации роутеров для предотвращения двойной регистрации.
# =============================================================================

from aiogram import Router

# __all__ определяет, какие имена будут экспортированы при "from . import *"
__all__ = [
    "start_router",
    "price_router",
    "asic_router",
    "news_router",
    "quiz_router",
    "market_router",
    "market_info_router",
    "verification_public_router",
    "achievements_router",
    "game_router",
    "menu_router",
    "crypto_center_router",
    "common_router",
    "public_router",  # Добавляем главный роутер в экспорт
]


def _safe_import(module_path: str, attr: str = "router") -> Router:
    """
    Безопасно импортирует модуль и возвращает объект Router.
    Если модуль/атрибут отсутствует, возвращает пустой Router.
    """
    try:
        module = __import__(module_path, fromlist=[attr])
        r = getattr(module, attr, None)
        if isinstance(r, Router):
            return r
    except ImportError: # Ловим именно ошибку импорта
        pass
    return Router(name=f"{module_path.rsplit('.', 1)[-1]}_empty")


def _safe_import_any(module_path: str, attrs: list[str]) -> Router:
    """
    Пытается получить любой Router из списка имен атрибутов.
    """
    try:
        module = __import__(module_path, fromlist=attrs)
        for attr in attrs:
            r = getattr(module, attr, None)
            if isinstance(r, Router):
                return r
    except ImportError:
        pass
    return Router(name=f"{module_path.rsplit('.', 1)[-1]}_empty")


def _is_empty_router(r: Router) -> bool:
    return isinstance(r, Router) and r.name.endswith("_empty")


# --- Безопасный импорт всех именованных роутеров ---
start_router = _safe_import("src.bot.handlers.public.start_handler")
price_router = _safe_import("src.bot.handlers.public.price_handler")
asic_router = _safe_import("src.bot.handlers.public.asic_handler")
news_router = _safe_import("src.bot.handlers.public.news_handler")
quiz_router = _safe_import("src.bot.handlers.public.quiz_handler")
market_router = _safe_import("src.bot.handlers.public.market_handler")
market_info_router = _safe_import("src.bot.handlers.public.market_info_handler")
verification_public_router = _safe_import("src.bot.handlers.public.verification_handler")
achievements_router = _safe_import("src.bot.handlers.public.achievements_handler")
game_router = _safe_import_any("src.bot.handlers.game", ["game_router", "router"])
_menu_try = _safe_import_any("src.bot.handlers.public.menu_handler", ["menu_router", "router"])
# ===============================================================
# ИСПРАВЛЕНИЕ ЗДЕСЬ: menu_router больше не дублирует start_router
# ===============================================================
menu_router = _menu_try if not _is_empty_router(_menu_try) else Router(name="menu_empty")
crypto_center_router = _safe_import("src.bot.handlers.public.crypto_center_handler")
common_router = _safe_import("src.bot.handlers.public.common_handler")

# --- СБОРКА ЕДИНОГО ПУБЛИЧНОГО РОУТЕРА ---
# Создаем главный роутер для всего модуля "public"
public_router = Router(name="public")

# Регистрируем все импортированные роутеры. Пустые роутеры не окажут влияния.
public_router.include_routers(
    start_router,
    price_router,
    asic_router,
    news_router,
    quiz_router,
    market_router,
    market_info_router,
    verification_public_router,
    achievements_router,
    game_router,
    menu_router,
    crypto_center_router,
    common_router,
)