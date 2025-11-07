# bot/services/advanced_security/inspectors/phrase_inspector.py
"""
Инспектор для анализа по базе знаний спам-фраз.
"""
from loguru import logger

from bot.services.advanced_security.inspectors.base import BaseInspector
from bot.services.advanced_security.models import InspectionResult


class PhraseInspector(BaseInspector):
    """
    Инспектор спам-фраз.
    
    Использует базу знаний (learning service) для проверки
    текста на схожесть с известными спам-фразами.
    """
    
    # Константы
    DEFAULT_MIN_RATIO = 85
    SCORE_DIVISOR = 3  # Делитель для преобразования ratio в score
    MAX_SCORE = 40  # Максимальная оценка от этого инспектора
    
    def __init__(self, config, learning_service, min_ratio: int = DEFAULT_MIN_RATIO):
        """
        Инициализация инспектора фраз.
        
        Args:
            config: Конфигурация безопасности
            learning_service: Сервис обучения с базой знаний
            min_ratio: Минимальный порог схожести (0-100)
        """
        super().__init__(config)
        self.learning_service = learning_service
        self.min_ratio = min_ratio
    
    async def inspect(self, text: str) -> InspectionResult:
        """
        Проверяет текст по базе знаний спам-фраз.
        
        Args:
            text: Текст для проверки
            
        Returns:
            Результат проверки с оценкой схожести
        """
        result = InspectionResult()
        
        if not text:
            return result
        
        try:
            # Получаем оценку от learning service
            score_ratio, scored_phrase = await self.learning_service.score_text(text)
            
            if score_ratio >= self.min_ratio and scored_phrase:
                # Преобразуем ratio (0-100) в score
                # Например, ratio=90 -> score=30
                calculated_score = min(
                    self.MAX_SCORE,
                    score_ratio // self.SCORE_DIVISOR
                )
                
                result.add_reason(
                    f"learned_phrase:'{scored_phrase.phrase[:50]}'",
                    calculated_score
                )
                
                result.metadata.update({
                    "matched_phrase": scored_phrase.phrase,
                    "similarity_ratio": score_ratio,
                    "confidence": scored_phrase.confidence
                })
                
                logger.info(
                    f"PhraseInspector: найдено совпадение "
                    f"(ratio: {score_ratio}, score: {calculated_score}, "
                    f"phrase: '{scored_phrase.phrase[:30]}...')"
                )
        
        except Exception as e:
            logger.error(f"Ошибка в PhraseInspector: {e}", exc_info=True)
        
        return result