# =============================================================================
# Файл: bot/handlers/public/__init__.py
# Версия: PRODUCTION-READY (29.10.2025) - Distinguished Engineer
# Описание:
#   • ИСПРАВЛЕНО: Добавлена регистрация всех роутеров в public_router
#   • ИСПРАВЛЕНО: Импорт всех handlers из модулей
#   • Теперь все команды будут обрабатываться
# =============================================================================

from aiogram import Router

# Создаем единый роутер для публичной части
public_router = Router(name="public_handlers")

# ==================== ИМПОРТ ВСЕХ HANDLERS ====================
# Импортируем роутеры из всех handler файлов
try:
    from .start_handler import router as start_router
    public_router.include_router(start_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import start_handler: {e}")

try:
    from .game_handler import router as game_router
    public_router.include_router(game_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import game_handler: {e}")

try:
    from .achievements_handler import router as achievements_router
    public_router.include_router(achievements_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import achievements_handler: {e}")

try:
    from .asic_handler import router as asic_router
    public_router.include_router(asic_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import asic_handler: {e}")

try:
    from .command_handler import router as command_router
    public_router.include_router(command_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import command_handler: {e}")

try:
    from .crypto_center_handler import router as crypto_center_router
    public_router.include_router(crypto_center_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import crypto_center_handler: {e}")

try:
    from .help_handler import router as help_router
    public_router.include_router(help_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import help_handler: {e}")

try:
    from .market_info_handler import router as market_info_router
    public_router.include_router(market_info_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import market_info_handler: {e}")

try:
    from .menu_handler import router as menu_router
    public_router.include_router(menu_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import menu_handler: {e}")

try:
    from .menu_handlers import router as menu_handlers_router
    public_router.include_router(menu_handlers_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import menu_handlers: {e}")

try:
    from .news_handler import router as news_router
    public_router.include_router(news_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import news_handler: {e}")

try:
    from .onboarding_handler import router as onboarding_router
    public_router.include_router(onboarding_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import onboarding_handler: {e}")

try:
    from .price_handler import router as price_router
    public_router.include_router(price_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import price_handler: {e}")

try:
    from .quiz_handler import router as quiz_router
    public_router.include_router(quiz_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import quiz_handler: {e}")

try:
    from .text_handler import router as text_router
    public_router.include_router(text_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import text_handler: {e}")

try:
    from .verification_public_handler import router as verification_router
    public_router.include_router(verification_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import verification_public_handler: {e}")

# Экспортируем public_router для использования в main.py
__all__ = ["public_router"]

print(f"✅ Public router configured with {len(public_router.sub_routers)} handlers")