# bot/services/antispam_learning.py
"""
DEPRECATED: Этот файл оставлен для обратной совместимости.
Используйте: from bot.services.antispam_learning import AntiSpamLearningService

Дата обновления: 07.11.2025
Версия: 3.0.0 (compatibility proxy)
"""

# Импортируем из нового модуля для обратной совместимости
from bot.services.antispam_learning.models import ScoredPhrase, SpamStatistics
from bot.services.antispam_learning.service import AntiSpamLearningService

# Алиас для обратной совместимости
AntiSpamLearning = AntiSpamLearningService

# Экспортируем для старых импортов
__all__ = [
    "AntiSpamLearningService",
    "AntiSpamLearning",
    "ScoredPhrase",
    "SpamStatistics",
]