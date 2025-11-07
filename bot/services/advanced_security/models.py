# bot/services/advanced_security/models.py
"""
Модели данных для системы безопасности.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InspectionResult:
    """
    Результат проверки одним инспектором.
    
    Attributes:
        score: Оценка угрозы (чем выше, тем опаснее)
        reasons: Список причин назначения оценки
        metadata: Дополнительные данные
    """
    score: int = 0
    reasons: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def add_reason(self, reason: str, score_increment: int = 0) -> None:
        """Добавляет причину и увеличивает оценку."""
        self.reasons.append(reason)
        self.score += score_increment
    
    def merge(self, other: "InspectionResult") -> None:
        """Объединяет с другим результатом."""
        self.score += other.score
        self.reasons.extend(other.reasons)
        self.metadata.update(other.metadata)


@dataclass
class ThreatMetrics:
    """
    Метрики угрозы для пользователя.
    
    Attributes:
        user_id: ID пользователя
        chat_id: ID чата
        strikes: Количество нарушений
        total_score: Общая оценка угрозы
        last_violation: Timestamp последнего нарушения
    """
    user_id: int
    chat_id: int
    strikes: int = 0
    total_score: int = 0
    last_violation: Optional[float] = None