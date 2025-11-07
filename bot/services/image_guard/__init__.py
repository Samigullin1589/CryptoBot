# bot/services/image_guard/__init__.py
"""
Модуль защиты от спам-изображений.

Компоненты:
- ImageGuardService - главный сервис защиты
- ImageVerdict - модель решения о действии
"""

from bot.services.image_guard.service import ImageGuardService
from bot.utils.models import ImageVerdict

__all__ = [
    "ImageGuardService",
    "ImageVerdict",
]