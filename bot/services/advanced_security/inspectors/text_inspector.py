# bot/services/advanced_security/inspectors/text_inspector.py
"""
Инспектор для анализа текстового контента.
"""
import re
from typing import Optional

from loguru import logger

from bot.services.advanced_security.inspectors.base import BaseInspector
from bot.services.advanced_security.models import InspectionResult


# Компилированные регулярные выражения
INVITE_LINK_PATTERN = re.compile(
    r"(t\.me/joinchat/|t\.me/\+|discord\.gg/|wa\.me/)",
    re.IGNORECASE
)


class TextInspector(BaseInspector):
    """
    Инспектор текстового контента.
    
    Проверяет текст на:
    - Подозрительные слова
    - Инвайт-ссылки
    - Чрезмерную длину
    """
    
    async def inspect(self, text: Optional[str]) -> InspectionResult:
        """
        Анализирует текст сообщения.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Результат проверки
        """
        result = InspectionResult()
        
        if not text:
            return result
        
        text_lower = text.lower()
        
        # Проверка подозрительных слов
        self._check_suspicious_words(text_lower, result)
        
        # Проверка инвайт-ссылок
        self._check_invite_links(text_lower, result)
        
        # Проверка длины текста
        self._check_text_length(text, result)
        
        if result.score > 0:
            logger.debug(
                f"TextInspector: score={result.score}, "
                f"reasons={result.reasons}"
            )
        
        return result
    
    def _check_suspicious_words(
        self,
        text_lower: str,
        result: InspectionResult
    ) -> None:
        """Проверяет наличие подозрительных слов."""
        suspicious_words = self.config.SUSPICIOUS_WORDS
        
        found_words = [
            word for word in suspicious_words
            if word in text_lower
        ]
        
        if found_words:
            result.add_reason(
                f"suspicious_words:{','.join(found_words[:3])}",
                self.config.HEURISTIC_WORD_SCORE
            )
            result.metadata["suspicious_words"] = found_words
    
    def _check_invite_links(
        self,
        text_lower: str,
        result: InspectionResult
    ) -> None:
        """Проверяет наличие инвайт-ссылок."""
        if INVITE_LINK_PATTERN.search(text_lower):
            result.add_reason(
                "invite_link",
                self.config.HEURISTIC_INVITE_SCORE
            )
            result.metadata["has_invite_link"] = True
    
    def _check_text_length(
        self,
        text: str,
        result: InspectionResult
    ) -> None:
        """Проверяет длину текста."""
        text_length = len(text)
        
        if text_length > self.config.MAX_TEXT_LENGTH:
            result.add_reason(
                f"long_text:{text_length}",
                self.config.HEURISTIC_LENGTH_SCORE
            )
            result.metadata["text_length"] = text_length