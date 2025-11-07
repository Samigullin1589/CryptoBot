# bot/services/antispam_learning/extractor.py
"""
Извлечение ключевых фраз из текста для анализа спама.
"""
from typing import List, Set

from loguru import logger


class TextPhraseExtractor:
    """
    Компонент для извлечения ключевых фраз из текста.
    
    Извлекает:
    - Отдельные значимые слова (токены)
    - Биграммы (пары соседних слов)
    - Триграммы (тройки соседних слов) - опционально
    """
    
    # Константы
    DEFAULT_MIN_TOKEN_LENGTH = 5
    DEFAULT_MAX_TOKENS = 50
    DEFAULT_MIN_PHRASE_LENGTH = 8
    DEFAULT_MAX_PHRASE_LENGTH = 64
    
    def __init__(
        self,
        min_token_length: int = DEFAULT_MIN_TOKEN_LENGTH,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        min_phrase_length: int = DEFAULT_MIN_PHRASE_LENGTH,
        max_phrase_length: int = DEFAULT_MAX_PHRASE_LENGTH,
        use_trigrams: bool = False
    ):
        """
        Инициализирует экстрактор фраз.
        
        Args:
            min_token_length: Минимальная длина токена
            max_tokens: Максимальное количество токенов для обработки
            min_phrase_length: Минимальная длина фразы
            max_phrase_length: Максимальная длина фразы
            use_trigrams: Извлекать триграммы
        """
        self.min_token_length = min_token_length
        self.max_tokens = max_tokens
        self.min_phrase_length = min_phrase_length
        self.max_phrase_length = max_phrase_length
        self.use_trigrams = use_trigrams
        
        logger.debug(
            f"🔧 TextPhraseExtractor инициализирован "
            f"(min_token: {min_token_length}, max_tokens: {max_tokens}, "
            f"trigrams: {use_trigrams})"
        )
    
    def extract_phrases(self, text: str) -> Set[str]:
        """
        Извлекает ключевые фразы из нормализованного текста.
        
        Args:
            text: Нормализованный текст (lowercase, без пунктуации)
            
        Returns:
            Набор уникальных фраз
        """
        if not text:
            return set()
        
        # Разбиваем на токены и фильтруем
        tokens = self._tokenize(text)
        
        if not tokens:
            return set()
        
        # Собираем фразы
        phrases = set()
        
        # 1. Добавляем отдельные токены
        phrases.update(tokens)
        
        # 2. Добавляем биграммы
        bigrams = self._extract_bigrams(tokens)
        phrases.update(bigrams)
        
        # 3. Добавляем триграммы (опционально)
        if self.use_trigrams:
            trigrams = self._extract_trigrams(tokens)
            phrases.update(trigrams)
        
        logger.debug(
            f"🔍 Извлечено фраз: {len(phrases)} "
            f"(токенов: {len(tokens)}, биграмм: {len(bigrams)})"
        )
        
        return phrases
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Разбивает текст на токены с фильтрацией.
        
        Args:
            text: Нормализованный текст
            
        Returns:
            Список отфильтрованных токенов
        """
        all_tokens = text.split()
        
        # Фильтруем токены по длине
        filtered = [
            token for token in all_tokens
            if len(token) >= self.min_token_length
        ]
        
        # Ограничиваем количество
        tokens = filtered[:self.max_tokens]
        
        return tokens
    
    def _extract_bigrams(self, tokens: List[str]) -> Set[str]:
        """
        Извлекает биграммы из токенов.
        
        Args:
            tokens: Список токенов
            
        Returns:
            Набор биграмм
        """
        bigrams = set()
        
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i + 1]}"
            
            # Фильтруем по длине
            if self.min_phrase_length <= len(bigram) <= self.max_phrase_length:
                bigrams.add(bigram)
        
        return bigrams
    
    def _extract_trigrams(self, tokens: List[str]) -> Set[str]:
        """
        Извлекает триграммы из токенов.
        
        Args:
            tokens: Список токенов
            
        Returns:
            Набор триграмм
        """
        trigrams = set()
        
        for i in range(len(tokens) - 2):
            trigram = f"{tokens[i]} {tokens[i + 1]} {tokens[i + 2]}"
            
            # Фильтруем по длине
            if self.min_phrase_length <= len(trigram) <= self.max_phrase_length:
                trigrams.add(trigram)
        
        return trigrams
    
    def extract_with_metadata(self, text: str) -> dict:
        """
        Извлекает фразы с метаданными для отладки.
        
        Args:
            text: Нормализованный текст
            
        Returns:
            Словарь с фразами и метаданными
        """
        tokens = self._tokenize(text)
        bigrams = self._extract_bigrams(tokens)
        
        metadata = {
            "total_phrases": len(tokens) + len(bigrams),
            "tokens": list(tokens),
            "bigrams": list(bigrams),
            "token_count": len(tokens),
            "bigram_count": len(bigrams),
        }
        
        if self.use_trigrams:
            trigrams = self._extract_trigrams(tokens)
            metadata["trigrams"] = list(trigrams)
            metadata["trigram_count"] = len(trigrams)
            metadata["total_phrases"] += len(trigrams)
        
        return metadata