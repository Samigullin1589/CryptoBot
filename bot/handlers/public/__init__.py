from aiogram import Router

__all__ = [
    "start_router",
    "price_router",
    "asic_router",
    "news_router",
    "quiz_router",
    "market_router",
    "market_info_router",
    "verification_public_router",
    "crypto_center_router",
    "common_router",
    "router",
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
    except Exception:
        pass
    return Router(name=f"{module_path.rsplit('.', 1)[-1]}_empty")


# Именованные роутеры (совместимость с dp.include_router(public.X_router))
start_router = _safe_import("bot.handlers.public.start_handler")
price_router = _safe_import("bot.handlers.public.price_handler")
asic_router = _safe_import("bot.handlers.public.asic_handler")
news_router = _safe_import("bot.handlers.public.news_handler")
quiz_router = _safe_import("bot.handlers.public.quiz_handler")
market_router = _safe_import("bot.handlers.public.market_handler")
market_info_router = _safe_import("bot.handlers.public.market_info_handler")
verification_public_router = _safe_import("bot.handlers.public.verification_handler")
crypto_center_router = _safe_import("bot.handlers.public.crypto_center_handler")
common_router = _safe_import("bot.handlers.public.common_handler")

# Плейсхолдер общего роутера, ничего не включает внутрь себя
router = Router(name="public")