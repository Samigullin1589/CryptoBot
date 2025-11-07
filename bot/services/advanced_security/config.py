# bot/services/advanced_security/config.py
"""
Конфигурация системы безопасности.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class SecurityConfig:
    """Конфигурация параметров безопасности."""
    
    # Пороги оценок для действий
    SCORE_DELETE: int = 15
    SCORE_WARN: int = 30
    SCORE_MUTE: int = 50
    SCORE_BAN: int = 70
    
    # Оценки за нарушения
    HEURISTIC_WORD_SCORE: int = 20
    HEURISTIC_INVITE_SCORE: int = 25
    HEURISTIC_LENGTH_SCORE: int = 10
    BAD_DOMAIN_SCORE: int = 40
    SUSPICIOUS_TLD_SCORE: int = 15
    IMAGE_SPAM_SCORE: int = 35
    
    # Настройки текста
    MAX_TEXT_LENGTH: int = 2000
    
    # Страйки и автобан
    STRIKES_FOR_AUTOBAN: int = 3
    REPEAT_WINDOW_SECONDS: int = 3600  # 1 час
    
    # Списки
    SUSPICIOUS_WORDS: List[str] = None
    SUSPICIOUS_TLDS: List[str] = None
    SAFE_DOMAINS: List[str] = None
    
    def __post_init__(self):
        """Инициализация списков по умолчанию."""
        if self.SUSPICIOUS_WORDS is None:
            self.SUSPICIOUS_WORDS = [
                "бесплатно", "заработок", "биткоин", "крипта",
                "инвестиц", "прибыль", "доход", "млн", "гарант"
            ]
        
        if self.SUSPICIOUS_TLDS is None:
            self.SUSPICIOUS_TLDS = [
                ".xyz", ".top", ".click", ".link", ".loan",
                ".download", ".stream", ".win", ".bid"
            ]
        
        if self.SAFE_DOMAINS is None:
            self.SAFE_DOMAINS = [
                "telegram.org", "t.me", "youtube.com",
                "github.com", "google.com"
            ]