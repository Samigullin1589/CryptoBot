# bot/services/image_guard_service.py
"""
DEPRECATED: Этот файл оставлен для обратной совместимости.
Используйте: from bot.services.image_guard import ImageGuardService

Дата обновления: 07.11.2025
Версия: 3.0.0 (compatibility proxy)
"""

# Импортируем из нового модуля для обратной совместимости
from bot.services.image_guard.service import ImageGuardService
from bot.utils.models import ImageVerdict

# Экспортируем для старых импортов
__all__ = [
    "ImageGuardService",
    "ImageVerdict",
]