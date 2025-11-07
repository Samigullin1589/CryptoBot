# bot/services/antispam_learning/scorer.py
"""
Оценка текста на схожесть со спамом с использованием нечеткого сравнения.
"""
from typing import List, Optional, Tuple

from loguru import logger
from rapidfuzz import fuzz, process

from bot.services.antispam_learning.models import ScoredPhrase


class SpamTextScorer:
    """
    Компонент для оценки текста на схожесть со спамом.
    
    Использует алгоритмы нечеткого сравнения строк (fuzzy matching)
    для определения схожести с известными спам-фразами.
    
    Поддерживаемые алгоритмы:
    - partial_ratio: Частичное совпадение
    - token_set_ratio: Совпадение токенов
    - token_sort_ratio: Совпадение с сортировкой
    """
    
    # Константы
    DEFAULT_MIN_RATIO = 80
    MIN_ALLOWED_RATIO = 50
    MAX_ALLOWED_RATIO = 100
    
    def __init__(
        self,
        min_ratio: int = DEFAULT_MIN_RATIO,
        scorer_type: str = "partial_ratio"
    ):
        """
        Инициализирует оценщик текста.
        
        Args:
            min_ratio: Минимальный порог схожести (50-100)
            scorer_type: Тип скорера ("partial_ratio", "token_set_ratio", "token_sort_ratio")
        
        Raises:
            ValueError: Если параметры некорректны
        """
        if not self.MIN_ALLOWED_RATIO <= min_ratio <= self.MAX_ALLOWED_RATIO:
            raise ValueError(
                f"min_ratio должен быть в диапазоне "
                f"[{self.MIN_ALLOWED_RATIO}, {self.MAX_ALLOWED_RATIO}]"
            )
        
        self.min_ratio = min_ratio
        self.scorer = self._get_scorer(scorer_type)
        self.scorer_type = scorer_type
        
        logger.debug(
            f"🔧 SpamTextScorer инициализирован "
            f"(min_ratio: {min_ratio}, scorer: {scorer_type})"
        )
    
    def _get_scorer(self, scorer_type: str):
        """
        Получает функцию скорера по типу.
        
        Args:
            scorer_type: Тип скорера
            
        Returns:
            Функция скорера
        """
        scorers = {
            "partial_ratio": fuzz.partial_ratio,
            "token_set_ratio": fuzz.token_set_ratio,
            "token_sort_ratio": fuzz.token_sort_ratio,
            "ratio": fuzz.ratio,
        }
        
        if scorer_type not in scorers:
            logger.warning(
                f"⚠️ Неизвестный тип скорера '{scorer_type}', "
                f"используется 'partial_ratio'"
            )
            return scorers["partial_ratio"]
        
        return scorers[scorer_type]
    
    def score(
        self,
        text: str,
        phrases: List[str]
    ) -> Tuple[int, Optional[ScoredPhrase]]:
        """
        Оценивает текст на схожесть с известными спам-фразами.
        
        Находит наиболее похожую фразу и возвращает оценку схожести.
        
        Args:
            text: Нормализованный текст для проверки
            phrases: Список известных спам-фраз
            
        Returns:
            Кортеж (оценка, совпавшая фраза или None)
        """
        if not text:
            logger.debug("⚠️ Пустой текст для оценки")
            return 0, None
        
        if not phrases:
            logger.debug("⚠️ Пустой список фраз для сравнения")
            return 0, None
        
        try:
            # Находим лучшее совпадение с использованием rapidfuzz
            result = process.extractOne(
                text,
                phrases,
                scorer=self.scorer,
                score_cutoff=self.min_ratio,
            )
            
            if result:
                phrase, score, _ = result
                
                # Вычисляем уверенность (confidence)
                confidence = self._calculate_confidence(score)
                
                scored_phrase = ScoredPhrase(
                    phrase=phrase,
                    score=float(score),
                    confidence=confidence
                )
                
                logger.info(
                    f"🎯 Найдено совпадение: '{phrase[:50]}...' "
                    f"(score: {score:.1f}%, confidence: {confidence:.2f})"
                )
                
                return int(score), scored_phrase
            
            logger.debug(
                f"✅ Совпадений не найдено "
                f"(min_ratio: {self.min_ratio})"
            )
            return 0, None
            
        except Exception as e:
            logger.error(f"❌ Ошибка оценки текста: {e}", exc_info=True)
            return 0, None
    
    def _calculate_confidence(self, score: float) -> float:
        """
        Вычисляет уверенность в оценке на основе score.
        
        Args:
            score: Оценка схожести (0-100)
            
        Returns:
            Уверенность (0.0-1.0)
        """
        # Простая линейная функция:
        # score 80 -> confidence 0.5
        # score 100 -> confidence 1.0
        if score >= 100:
            return 1.0
        if score <= self.min_ratio:
            return 0.5
        
        # Линейная интерполяция
        range_score = 100 - self.min_ratio
        normalized = (score - self.min_ratio) / range_score
        
        return 0.5 + (normalized * 0.5)
    
    def score_multiple(
        self,
        text: str,
        phrases: List[str],
        limit: int = 5
    ) -> List[ScoredPhrase]:
        """
        Находит несколько наиболее похожих фраз.
        
        Args:
            text: Нормализованный текст
            phrases: Список спам-фраз
            limit: Количество результатов
            
        Returns:
            Список оцененных фраз
        """
        if not text or not phrases:
            return []
        
        try:
            results = process.extract(
                text,
                phrases,
                scorer=self.scorer,
                score_cutoff=self.min_ratio,
                limit=limit
            )
            
            scored_phrases = []
            for phrase, score, _ in results:
                confidence = self._calculate_confidence(score)
                scored_phrases.append(
                    ScoredPhrase(
                        phrase=phrase,
                        score=float(score),
                        confidence=confidence
                    )
                )
            
            return scored_phrases
            
        except Exception as e:
            logger.error(f"❌ Ошибка множественной оценки: {e}", exc_info=True)
            return []