# bot/containers/wiring.py
"""
Конфигурация wiring для dependency-injector.
Версия: 3.0.0 Production (07.11.2025)

Список всех модулей для автоматического внедрения зависимостей.
"""

WIRING_MODULES = [
    # Middlewares
    "bot.middlewares.dependencies",
    
    # Public Handlers
    "bot.handlers.public.commands",
    "bot.handlers.public.command_handler_extended",
    "bot.handlers.public.common_handler",
    "bot.handlers.public.price_handler",
    "bot.handlers.public.asic_handler",
    "bot.handlers.public.news_handler",
    "bot.handlers.public.market_handler",
    "bot.handlers.public.market_info_handler",
    "bot.handlers.public.crypto_center_handler",
    "bot.handlers.public.achievements_handler",
    "bot.handlers.public.menu_handler",
    "bot.handlers.public.help_handler",
    "bot.handlers.public.start_handler",
    "bot.handlers.public.text_handler",
    "bot.handlers.public.verification_public_handler",
    "bot.handlers.public.onboarding_handler",
    
    # Game Handlers
    "bot.handlers.game.game_handler",
    "bot.handlers.game.mining_game_handler",
    
    # Admin Handlers
    "bot.handlers.admin.admin_handler",
    "bot.handlers.admin.admin_menu",
    "bot.handlers.admin.cache_handler",
    "bot.handlers.admin.game_admin_handler",
    "bot.handlers.admin.health_handler",
    "bot.handlers.admin.moderation_handler",
    "bot.handlers.admin.stats_handler",
    "bot.handlers.admin.verification_admin_handler",
    "bot.handlers.admin.version_handler",
    
    # Tools Handlers
    "bot.handlers.tools.calculator_handler",
    
    # Threats Handlers
    "bot.handlers.threats.threat_handler",
]

__all__ = ["WIRING_MODULES"]