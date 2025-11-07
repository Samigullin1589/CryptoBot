# bot/services/ai/__init__.py
"""
Модуль AI сервисов для работы с различными провайдерами LLM.

Компоненты:
- AIContentService - главный сервис для работы с AI
- AIService - алиас для обратной совместимости
"""

from bot.services.ai.service import AIContentService

# Алиас для обратной совместимости
AIService = AIContentService

__all__ = [
    "AIContentService",
    "AIService",  # Backward compatibility
]