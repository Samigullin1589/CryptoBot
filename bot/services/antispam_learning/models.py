# bot/services/antispam_learning/models.py
"""
Модели данных для системы антиспама.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScoredPhrase:
    """
    Спам-фраза с оценкой схожести.
    
    Attributes:
        phrase: Текст спам-фразы
        score: Оценка схожести (0-100)
        confidence: Уверенность в оценке (0.0-1.0)
    """
    phrase: str
    score: float
    confidence: float = 1.0
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Проверяет высокую уверенность в оценке."""
        return self.confidence >= threshold


@dataclass(frozen=True)
class SpamStatistics:
    """
    Статистика базы знаний антиспама.
    
    Attributes:
        phrases_count: Количество известных спам-фраз
        domains_count: Количество известных спам-доменов
        samples_count: Количество сохраненных примеров спама
        cache_valid: Валидность кэша
        cache_size: Размер кэша
    """
    phrases_count: int
    domains_count: int
    samples_count: int
    cache_valid: bool
    cache_size: int
    
    def to_dict(self) -> dict:
        """Преобразует статистику в словарь."""
        return {
            "phrases_count": self.phrases_count,
            "domains_count": self.domains_count,
            "samples_count": self.samples_count,
            "cache_valid": self.cache_valid,
            "cache_size": self.cache_size,
        }


@dataclass
class SpamPhrase:
    """
    Спам-фраза с метаданными.
    
    Attributes:
        text: Текст фразы
        frequency: Частота встречаемости
        last_seen: Timestamp последнего обнаружения
    """
    text: str
    frequency: float
    last_seen: Optional[float] = None