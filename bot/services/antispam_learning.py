# bot/services/antispam_learning.py
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from loguru import logger
from rapidfuzz import fuzz
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.keys import KeyFactory
from bot.utils.text_utils import normalize_text


@dataclass(frozen=True)
class ScoredPhrase:
    """
    Спам-фраза с оценкой схожести.
    
    Attributes:
        phrase: Текст фразы
        score: Оценка схожести (0-100)
    """
    phrase: str
    score: float


class SpamPhraseCache:
    """
    Кэш топ спам-фраз для оптимизации производительности.
    
    Уменьшает количество обращений к Redis путем локального кэширования
    наиболее частых спам-фраз.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Инициализирует кэш фраз.
        
        Args:
            ttl_seconds: Время жизни кэша в секундах
        """
        self._phrases: List[str] = []
        self._expiry_time: float = 0.0
        self._ttl_seconds = ttl_seconds
    
    def get(self) -> Optional[List[str]]:
        """
        Получает закэшированные фразы если кэш валиден.
        
        Returns:
            Optional[List[str]]: Список фраз или None если кэш устарел
        """
        if not self.is_valid():
            return None
        return self._phrases.copy()
    
    def set(self, phrases: List[str]) -> None:
        """
        Сохраняет фразы в кэш.
        
        Args:
            phrases: Список фраз для кэширования
        """
        self._phrases = phrases
        self._expiry_time = time.monotonic() + self._ttl_seconds
        logger.debug(f"📦 Кэш обновлен: {len(phrases)} фраз")
    
    def is_valid(self) -> bool:
        """
        Проверяет валидность кэша.
        
        Returns:
            bool: True если кэш актуален
        """
        return time.monotonic() < self._expiry_time and bool(self._phrases)
    
    def invalidate(self) -> None:
        """Принудительно инвалидирует кэш."""
        self._expiry_time = 0.0
        self._phrases = []
        logger.debug("🔄 Кэш фраз инвалидирован")


class TextPhraseExtractor:
    """
    Компонент для извлечения ключевых фраз из текста.
    
    Извлекает отдельные слова и биграммы для анализа спама.
    """
    
    @staticmethod
    def extract_phrases(text: str, max_tokens: int = 50) -> set[str]:
        """
        Извлекает ключевые фразы из текста.
        
        Args:
            text: Нормализованный текст
            max_tokens: Максимальное количество токенов
            
        Returns:
            set[str]: Набор уникальных фраз
        """
        if not text:
            return set()
        
        tokens = [
            token for token in text.split()
            if len(token) >= 5
        ][:max_tokens]
        
        phrases = set(tokens)
        
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i + 1]}"
            if 8 <= len(bigram) <= 64:
                phrases.add(bigram)
        
        return phrases


class SpamKnowledgeBase:
    """
    База знаний о спаме в Redis.
    
    Управляет хранением и обновлением информации о спам-фразах,
    доменах и примерах спама.
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует базу знаний.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.keys = KeyFactory
        self.config = settings.security
    
    async def add_phrases(self, phrases: set[str]) -> int:
        """
        Добавляет фразы в базу знаний.
        
        Args:
            phrases: Набор фраз для добавления
            
        Returns:
            int: Количество добавленных фраз
        """
        if not phrases:
            return 0
        
        try:
            pipe = self.redis.pipeline()
            
            for phrase in phrases:
                pipe.zincrby(self.keys.spam_phrases(), 1.0, phrase)
            
            max_phrases = getattr(self.config, 'learning_max_phrases', 10000)
            pipe.zremrangebyrank(
                self.keys.spam_phrases(),
                0,
                -(max_phrases + 1)
            )
            
            await pipe.execute()
            return len(phrases)
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления фраз: {e}")
            return 0
    
    async def add_domains(self, domains: Iterable[str]) -> int:
        """
        Добавляет домены в базу знаний.
        
        Args:
            domains: Список доменов
            
        Returns:
            int: Количество добавленных доменов
        """
        domains_list = list(domains)
        if not domains_list:
            return 0
        
        try:
            pipe = self.redis.pipeline()
            
            for domain in domains_list:
                pipe.zincrby(self.keys.spam_domains(), 1.0, domain.lower())
            
            max_domains = getattr(self.config, 'learning_max_domains', 5000)
            pipe.zremrangebyrank(
                self.keys.spam_domains(),
                0,
                -(max_domains + 1)
            )
            
            await pipe.execute()
            return len(domains_list)
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления доменов: {e}")
            return 0
    
    async def add_sample(self, text: str) -> bool:
        """
        Сохраняет пример спама.
        
        Args:
            text: Текст спама
            
        Returns:
            bool: True если успешно сохранено
        """
        try:
            pipe = self.redis.pipeline()
            
            pipe.lpush(self.keys.spam_samples(), text[:2000])
            
            max_samples = getattr(self.config, 'learning_max_samples', 1000)
            pipe.ltrim(self.keys.spam_samples(), 0, max_samples - 1)
            
            await pipe.execute()
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения примера: {e}")
            return False
    
    async def get_top_phrases(self, limit: int) -> List[str]:
        """
        Получает топ спам-фраз из базы.
        
        Args:
            limit: Количество фраз
            
        Returns:
            List[str]: Список фраз
        """
        try:
            phrases_bytes = await self.redis.zrevrange(
                self.keys.spam_phrases(),
                0,
                limit - 1
            )
            return [p.decode("utf-8", "ignore") for p in phrases_bytes]
        except Exception as e:
            logger.error(f"❌ Ошибка получения фраз: {e}")
            return []
    
    async def get_domain_score(self, domain: str) -> float:
        """
        Получает оценку домена из базы.
        
        Args:
            domain: Доменное имя
            
        Returns:
            float: Оценка домена
        """
        try:
            score = await self.redis.zscore(
                self.keys.spam_domains(),
                domain.lower()
            )
            return score or 0.0
        except Exception as e:
            logger.error(f"❌ Ошибка проверки домена '{domain}': {e}")
            return 0.0


class SpamTextScorer:
    """
    Компонент для оценки текста на схожесть со спамом.
    
    Использует нечеткое сравнение строк для определения схожести
    с известными спам-фразами.
    """
    
    def __init__(self, min_ratio: int = 80):
        """
        Инициализирует оценщик текста.
        
        Args:
            min_ratio: Минимальный порог схожести (0-100)
        """
        self.min_ratio = min_ratio
    
    def score(self, text: str, phrases: List[str]) -> Tuple[int, Optional[ScoredPhrase]]:
        """
        Оценивает текст на схожесть с известными спам-фразами.
        
        Args:
            text: Нормализованный текст
            phrases: Список известных спам-фраз
            
        Returns:
            Tuple[int, Optional[ScoredPhrase]]: Максимальный скор и фраза
        """
        if not text or not phrases:
            return 0, None
        
        best_match = fuzz.process.extractOne(
            text,
            phrases,
            scorer=fuzz.partial_ratio,
            score_cutoff=self.min_ratio,
        )
        
        if best_match:
            phrase, score, _ = best_match
            logger.debug(f"🎯 Найдено совпадение: '{phrase}' ({score:.1f}%)")
            return int(score), ScoredPhrase(phrase, float(score))
        
        return 0, None


class AntiSpamLearningService:
    """
    Самообучаемая система антиспама.
    
    Хранит и анализирует спам-фразы и домены, обучается на основе
    обратной связи от администраторов.
    
    Архитектура:
    - Кэширование для производительности
    - База знаний в Redis
    - Нечеткое сравнение строк
    - Извлечение ключевых фраз
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует сервис обучения.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.config = settings.security
        
        cache_ttl = getattr(self.config, 'learning_cache_ttl_seconds', 300)
        self.cache = SpamPhraseCache(ttl_seconds=cache_ttl)
        
        self.knowledge_base = SpamKnowledgeBase(redis)
        
        min_ratio = getattr(self.config, 'learning_min_ratio', 80)
        self.scorer = SpamTextScorer(min_ratio=min_ratio)
        
        self.phrase_extractor = TextPhraseExtractor()
        
        logger.info("✅ Сервис AntiSpamLearningService инициализирован.")
    
    async def add_feedback(
        self,
        text: str,
        domains: Optional[Iterable[str]] = None
    ) -> None:
        """
        Обучает систему на примере спама.
        
        Вызывается после подтверждения спама администратором.
        
        Args:
            text: Текст спама
            domains: Опциональные домены из текста
        """
        normalized = normalize_text(text)
        
        if not normalized:
            logger.warning("⚠️ Пустой текст для обучения")
            return
        
        phrases = self.phrase_extractor.extract_phrases(normalized)
        
        phrases_added = await self.knowledge_base.add_phrases(phrases)
        domains_added = 0
        
        if domains:
            domains_added = await self.knowledge_base.add_domains(domains)
        
        await self.knowledge_base.add_sample(text)
        
        self.cache.invalidate()
        
        logger.success(
            f"✅ База обновлена: {phrases_added} фраз, "
            f"{domains_added} доменов"
        )
    
    async def score_text(self, text: str) -> Tuple[int, Optional[ScoredPhrase]]:
        """
        Оценивает текст на схожесть с известным спамом.
        
        Args:
            text: Текст для проверки
            
        Returns:
            Tuple[int, Optional[ScoredPhrase]]: Оценка и совпавшая фраза
        """
        normalized = normalize_text(text)
        
        if not normalized:
            return 0, None
        
        phrases = await self._get_cached_phrases()
        
        if not phrases:
            return 0, None
        
        return self.scorer.score(normalized, phrases)
    
    async def is_bad_domain(self, host: str) -> bool:
        """
        Проверяет домен на присутствие в черном списке.
        
        Args:
            host: Доменное имя
            
        Returns:
            bool: True если домен в черном списке
        """
        if not host:
            return False
        
        score = await self.knowledge_base.get_domain_score(host)
        
        min_score = getattr(self.config, 'learning_domain_min_score', 3.0)
        
        is_bad = score >= min_score
        
        if is_bad:
            logger.warning(f"⚠️ Плохой домен: {host} (оценка: {score})")
        
        return is_bad
    
    async def _get_cached_phrases(self) -> List[str]:
        """
        Получает список фраз с использованием кэша.
        
        Returns:
            List[str]: Список спам-фраз
        """
        cached = self.cache.get()
        
        if cached is not None:
            return cached
        
        top_k = getattr(self.config, 'learning_top_k', 500)
        phrases = await self.knowledge_base.get_top_phrases(top_k)
        
        if phrases:
            self.cache.set(phrases)
        
        return phrases
    
    async def get_statistics(self) -> dict:
        """
        Получает статистику базы знаний.
        
        Returns:
            dict: Статистика
        """
        try:
            pipe = self.redis.pipeline()
            pipe.zcard(self.keys.spam_phrases())
            pipe.zcard(self.keys.spam_domains())
            pipe.llen(self.keys.spam_samples())
            
            results = await pipe.execute()
            
            return {
                "phrases_count": results[0],
                "domains_count": results[1],
                "samples_count": results[2],
                "cache_valid": self.cache.is_valid(),
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}