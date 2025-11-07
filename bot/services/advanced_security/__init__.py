# bot/services/advanced_security/__init__.py
"""
Модуль продвинутой системы безопасности.

Компоненты:
- AdvancedSecurityService - главный сервис безопасности
- SecurityVerdict - модель вердикта проверки
"""

from bot.services.advanced_security.service import AdvancedSecurityService

__all__ = [
    "AdvancedSecurityService",
]