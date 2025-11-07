# bot/services/antispam_learning/service.py
"""
Главный сервис самообучаемой системы антиспама.
"""
from typing import Iterable, Optional, Tuple

from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.antispam_learning.cache import SpamPhraseCache
from bot.services.antispam_learning.extractor import TextPhraseExtractor
from bot.services.antispam_learning.knowledge_base import SpamKnowledgeBase
from bot.services.antispam_learning.models import ScoredPhrase, SpamStatistics
from bot.services.antispam_learning.scorer import SpamTextScorer
from bot.utils.text_utils import normalize_text


class AntiSpamLearningService:
    """
    Самообучаемая система антиспама.
    
    Основные возможности:
    - Обучение на примерах спама с обратной связью
    - Хранение и анализ спам-фраз и доменов
    - Кэширование для производительности
    - Нечеткое сравнение текста с известными паттернами
    - Статистика и метрики
    
    Архитектура:
    ┌────────────────────────────────────┐
    │  AntiSpamLearningService (Фасад)  │
    └────────────────────────────────────┘
              ↓           ↓           ↓
    ┌──────────────┐ ┌───────────┐ ┌───────────────┐
    │ Cache        │ │ Knowledge │ │ Scorer        │
    │ (Local)      │ │ Base      │ │ (Fuzzy Match) │
    │              │ │ (Redis)   │ │               │
    └──────────────┘ └───────────┘ └───────────────┘
              ↓
    ┌────────────────────┐
    │ Phrase Extractor   │
    │ (N-grams)          │
    └────────────────────┘
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует сервис антиспама.
        
        Args:
            redis: Клиент Redis для хранения данных
        """
        self.redis = redis
        self.config = settings.security
        
        # Инициализация компонентов
        self._init_cache()
        self._init_knowledge_base()
        self._init_scorer()
        self._init_extractor()
        
        logger.success("✅ Сервис AntiSpamLearningService инициализирован")
    
    def _init_cache(self) -> None:
        """Инициализирует кэш фраз."""
        cache_ttl = getattr(self.config, 'learning_cache_ttl_seconds', 300)
        self.cache = SpamPhraseCache(ttl_seconds=cache_ttl)
    
    def _init_knowledge_base(self) -> None:
        """Инициализирует базу знаний."""
        self.knowledge_base = SpamKnowledgeBase(self.redis)
    
    def _init_scorer(self) -> None:
        """Инициализирует скорер текста."""
        min_ratio = getattr(self.config, 'learning_min_ratio', 80)
        scorer_type = getattr(self.config, 'learning_scorer_type', 'partial_ratio')
        
        self.scorer = SpamTextScorer(
            min_ratio=min_ratio,
            scorer_type=scorer_type
        )
    
    def _init_extractor(self) -> None:
        """Инициализирует экстрактор фраз."""
        use_trigrams = getattr(self.config, 'learning_use_trigrams', False)
        
        self.extractor = TextPhraseExtractor(use_trigrams=use_trigrams)
    
    async def add_feedback(
        self,
        text: str,
        domains: Optional[Iterable[str]] = None
    ) -> None:
        """
        Обучает систему на примере спама.
        
        Вызывается администратором после подтверждения спама.
        Извлекает ключевые фразы и сохраняет их в базу знаний.
        
        Args:
            text: Текст спама
            domains: Опциональные домены из текста
        """
        if not text:
            logger.warning("⚠️ Попытка обучения на пустом тексте")
            return
        
        # Нормализуем текст
        normalized = normalize_text(text)
        
        if not normalized:
            logger.warning("⚠️ Текст стал пустым после нормализации")
            return
        
        # Извлекаем фразы
        phrases = self.extractor.extract_phrases(normalized)
        
        if not phrases:
            logger.warning("⚠️ Не удалось извлечь фразы из текста")
            return
        
        # Добавляем фразы в базу
        phrases_added = await self.knowledge_base.add_phrases(phrases)
        
        # Добавляем домены если есть
        domains_added = 0
        if domains:
            domains_added = await self.knowledge_base.add_domains(domains)
        
        # Сохраняем пример
        await self.knowledge_base.add_sample(text)
        
        # Инвалидируем кэш для обновления
        self.cache.invalidate()
        
        logger.success(
            f"✅ База обновлена: {phrases_added} фраз, "
            f"{domains_added} доменов добавлено"
        )
    
    async def score_text(self, text: str) -> Tuple[int, Optional[ScoredPhrase]]:
        """
        Оценивает текст на схожесть с известным спамом.
        
        Args:
            text: Текст для проверки
            
        Returns:
            Кортеж (оценка 0-100, совпавшая фраза или None)
        """
        if not text:
            return 0, None
        
        # Нормализуем текст
        normalized = normalize_text(text)
        
        if not normalized:
            return 0, None
        
        # Получаем список фраз (с кэшированием)
        phrases = await self._get_cached_phrases()
        
        if not phrases:
            logger.debug("ℹ️ База знаний пуста, оценка невозможна")
            return 0, None
        
        # Оцениваем текст
        return self.scorer.score(normalized, phrases)
    
    async def is_bad_domain(self, host: str) -> bool:
        """
        Проверяет домен на присутствие в черном списке.
        
        Args:
            host: Доменное имя
            
        Returns:
            True если домен в черном списке
        """
        if not host:
            return False
        
        # Получаем оценку домена
        score = await self.knowledge_base.get_domain_score(host)
        
        # Проверяем по порогу
        min_score = getattr(self.config, 'learning_domain_min_score', 3.0)
        is_bad = score >= min_score
        
        if is_bad:
            logger.warning(
                f"⚠️ Обнаружен плохой домен: {host} "
                f"(оценка: {score:.1f}, порог: {min_score})"
            )
        
        return is_bad
    
    async def get_domain_score(self, host: str) -> float:
        """
        Получает оценку домена.
        
        Args:
            host: Доменное имя
            
        Returns:
            Оценка домена (0.0 если не найден)
        """
        return await self.knowledge_base.get_domain_score(host)
    
    async def _get_cached_phrases(self) -> list[str]:
        """
        Получает список фраз с использованием кэша.
        
        Returns:
            Список спам-фраз
        """
        # Пытаемся получить из кэша
        cached = self.cache.get()
        
        if cached is not None:
            return cached
        
        # Кэш пуст или устарел - загружаем из базы
        top_k = getattr(self.config, 'learning_top_k', 500)
        phrases = await self.knowledge_base.get_top_phrases(top_k)
        
        if phrases:
            # Обновляем кэш
            self.cache.set(phrases)
            logger.info(f"📦 Кэш обновлен из базы знаний: {len(phrases)} фраз")
        else:
            logger.warning("⚠️ База знаний пуста")
        
        return phrases
    
    async def get_statistics(self) -> SpamStatistics:
        """
        Получает статистику базы знаний и системы.
        
        Returns:
            Объект статистики
        """
        try:
            # Получаем данные из базы
            phrases_count = await self.knowledge_base.get_phrase_count()
            domains_count = await self.knowledge_base.get_domain_count()
            samples_count = await self.knowledge_base.get_sample_count()
            
            # Получаем состояние кэша
            cache_stats = self.cache.get_stats()
            
            stats = SpamStatistics(
                phrases_count=phrases_count,
                domains_count=domains_count,
                samples_count=samples_count,
                cache_valid=cache_stats["valid"],
                cache_size=cache_stats["size"]
            )
            
            logger.debug(f"📊 Статистика: {stats.to_dict()}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}", exc_info=True)
            
            # Возвращаем пустую статистику
            return SpamStatistics(
                phrases_count=0,
                domains_count=0,
                samples_count=0,
                cache_valid=False,
                cache_size=0
            )
    
    async def invalidate_cache(self) -> None:
        """Принудительно инвалидирует кэш."""
        self.cache.invalidate()
        logger.info("🔄 Кэш инвалидирован по запросу")
    
    def get_cache_stats(self) -> dict:
        """Возвращает детальную статистику кэша."""
        return self.cache.get_stats()