# bot/services/antispam_learning/__init__.py
"""
Модуль самообучаемой системы антиспама.

Компоненты:
- AntiSpamLearningService - главный сервис
- ScoredPhrase - модель оцененной фразы
- SpamStatistics - статистика базы знаний
"""

from bot.services.antispam_learning.models import ScoredPhrase, SpamStatistics
from bot.services.antispam_learning.service import AntiSpamLearningService

# Алиас для обратной совместимости
AntiSpamLearning = AntiSpamLearningService

__all__ = [
    "AntiSpamLearningService",
    "AntiSpamLearning",  # Обратная совместимость
    "ScoredPhrase",
    "SpamStatistics",
]