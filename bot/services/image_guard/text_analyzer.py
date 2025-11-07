# bot/services/image_guard/text_analyzer.py
"""
Анализ текста на спам-признаки.
"""
import re
from typing import Pattern

from loguru import logger

from bot.config.settings import settings


class SpamTextAnalyzer:
    """
    Компонент для анализа текста на спам-признаки.
    
    Использует:
    - Регулярные выражения для спам-паттернов
    - Эвристические правила (emoji, ссылки, упоминания)
    """
    
    def __init__(self):
        """Инициализирует анализатор текста."""
        self.config = settings.security
        self._spam_pattern = self._compile_spam_pattern()
        
        logger.debug("🔧 SpamTextAnalyzer инициализирован")
    
    def _compile_spam_pattern(self) -> Pattern:
        """
        Компилирует регулярное выражение для поиска спам-паттернов.
        
        Returns:
            Скомпилированное регулярное выражение
        """
        # Получаем паттерны из конфига или используем дефолтные
        patterns = getattr(self.config, 'image_spam_patterns', None)
        
        if not patterns:
            patterns = [
                r'заработ[ок]',
                r'пассивн[ыо][йе]?\s+доход',
                r'легк[ие][е]?\s+деньг[и]',
                r'миллион',
                r'крипт[оа]валют',
                r'инвестиц',
                r'бинанс',
                r'трейдинг',
            ]
        
        combined_pattern = "|".join(patterns)
        
        logger.debug(f"📝 Загружено {len(patterns)} спам-паттернов")
        
        return re.compile(combined_pattern, re.IGNORECASE)
    
    def is_spam(self, text: str) -> bool:
        """
        Проверяет текст на спам-признаки.
        
        Args:
            text: Текст для анализа
            
        Returns:
            True если текст похож на спам
        """
        if not text or not text.strip():
            return False
        
        # Проверка по паттернам
        if self._spam_pattern.search(text):
            logger.info(f"🚨 Спам обнаружен по паттерну в тексте")
            return True
        
        # Эвристическая проверка
        if self._check_spam_heuristics(text):
            logger.info(f"🚨 Спам обнаружен по эвристике")
            return True
        
        return False
    
    def _check_spam_heuristics(self, text: str) -> bool:
        """
        Применяет эвристические правила для определения спама.
        
        Оценивает:
        - Количество денежных emoji (💰💵🪙$€₽₿)
        - Количество ссылок
        - Количество упоминаний пользователей
        
        Args:
            text: Текст для анализа
            
        Returns:
            True если обнаружены признаки спама
        """
        # Подсчет различных индикаторов
        money_marks = len(re.findall(r"[💰💵🪙\$€₽₿₮]", text))
        links = len(re.findall(r"https?://|t\.me/", text, re.IGNORECASE))
        mentions = len(re.findall(r"@\w{4,}", text))
        
        # Вычисляем взвешенный score
        # Денежные символы важнее всего
        score = (money_marks * 2) + (links * 1.5) + mentions
        
        # Получаем порог из конфига
        threshold = getattr(self.config, 'image_text_spam_score', 5)
        
        logger.debug(
            f"📊 Эвристический анализ: score={score:.1f}, "
            f"threshold={threshold} (money={money_marks}, "
            f"links={links}, mentions={mentions})"
        )
        
        return score >= threshold
    
    def get_spam_score(self, text: str) -> float:
        """
        Вычисляет числовую оценку спамности текста.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Оценка спамности (0.0 - не спам, выше - более подозрительно)
        """
        if not text or not text.strip():
            return 0.0
        
        score = 0.0
        
        # Оценка по паттернам
        matches = len(self._spam_pattern.findall(text))
        score += matches * 10.0
        
        # Эвристическая оценка
        money_marks = len(re.findall(r"[💰💵🪙\$€₽₿₮]", text))
        links = len(re.findall(r"https?://|t\.me/", text, re.IGNORECASE))
        mentions = len(re.findall(r"@\w{4,}", text))
        
        score += (money_marks * 2) + (links * 1.5) + mentions
        
        return score