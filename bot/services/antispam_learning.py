# bot/services/antispam_learning.py
# Дата обновления: 19.08.2025
# Версия: 2.0.0
# Описание: Сервис для самообучаемой памяти антиспам-системы,
# хранящий и анализирующий спам-фразы и домены с использованием Redis.

import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from loguru import logger
from rapidfuzz import fuzz
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.text_utils import normalize_text


@dataclass(frozen=True)
class ScoredPhrase:
    """Представляет спам-фразу и её оценку схожести с проверяемым текстом."""
    phrase: str
    score: float


class AntiSpamLearning:
    """
    Управляет базой знаний о спаме (фразы, домены), хранящейся в Redis.
    Позволяет добавлять новые данные (обучаться на действиях админов) и
    оценивать новый контент на схожесть с известными спам-паттернами.
    """

    def __init__(self):
        """Инициализирует сервис и его внутренний кэш."""
        self.redis: Redis = get_redis_client()
        self.keys = KeyFactory
        self.config = settings.SECURITY

        # Внутренний кэш для топ-фраз, чтобы не обращаться к Redis на каждое сообщение
        self._phrase_cache: List[str] = []
        self._cache_expiry_time: float = 0.0
        logger.info("Сервис AntiSpamLearning инициализирован.")

    async def _get_top_phrases(self) -> List[str]:
        """
        Возвращает кэшированный список топ-фраз. Если кэш устарел,
        обновляет его из Redis. Это ключевая оптимизация производительности.
        """
        current_time = time.monotonic()
        if current_time > self._cache_expiry_time or not self._phrase_cache:
            try:
                phrases_bytes = await self.redis.zrevrange(
                    self.keys.spam_phrases(), 0, self.config.LEARNING_TOP_K - 1
                )
                self._phrase_cache = [p.decode("utf-8", "ignore") for p in phrases_bytes]
                self._cache_expiry_time = current_time + self.config.LEARNING_CACHE_TTL_SECONDS
                logger.debug(f"Кэш спам-фраз обновлен. Загружено {len(self._phrase_cache)} фраз.")
            except Exception as e:
                logger.error(f"Не удалось обновить кэш спам-фраз из Redis: {e}")
                # В случае ошибки возвращаем старый кэш, если он есть
                return self._phrase_cache
        return self._phrase_cache

    def _invalidate_phrase_cache(self):
        """Сбрасывает кэш фраз, чтобы при следующем запросе он был обновлен."""
        self._cache_expiry_time = 0.0
        self._phrase_cache = []
        logger.info("Кэш спам-фраз был инвалидирован.")

    async def add_feedback(self, text: str, domains: Optional[Iterable[str]] = None):
        """
        Добавляет данные о спаме в базу знаний. Вызывается после подтверждения
        спама администратором.
        """
        normalized = normalize_text(text)
        if not normalized:
            return

        # Извлекаем ключевые фразы (отдельные слова и пары слов)
        tokens = [t for t in normalized.split() if len(t) >= 5][:50]
        phrases = set(tokens)
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i+1]}"
            if 8 <= len(bigram) <= 64:
                phrases.add(bigram)

        try:
            pipe = self.redis.pipeline()
            # Обновляем веса фраз
            if phrases:
                for p in phrases:
                    pipe.zincrby(self.keys.spam_phrases(), 1.0, p)
            
            # Обновляем веса доменов
            if domains:
                for d in domains:
                    pipe.zincrby(self.keys.spam_domains(), 1.0, d.lower())

            # Ограничиваем размер ZSET, чтобы они не росли бесконечно
            pipe.zremrangebyrank(self.keys.spam_phrases(), 0, -(self.config.LEARNING_MAX_PHRASES + 1))
            pipe.zremrangebyrank(self.keys.spam_domains(), 0, -(self.config.LEARNING_MAX_DOMAINS + 1))
            
            # Сохраняем пример спама для анализа
            pipe.lpush(self.keys.spam_samples(), text[:2000])
            pipe.ltrim(self.keys.spam_samples(), 0, self.config.LEARNING_MAX_SAMPLES - 1)
            
            await pipe.execute()
            self._invalidate_phrase_cache() # Сбрасываем кэш после обновления
            logger.success(f"База знаний обновлена. Добавлено {len(phrases)} фраз и {len(domains or [])} доменов.")
        except Exception as e:
            logger.exception(f"Ошибка при добавлении данных в базу знаний: {e}")

    async def score_text(self, text: str) -> Tuple[int, Optional[ScoredPhrase]]:
        """
        Сравнивает текст с базой знаний спам-фраз и возвращает максимальный
        процент схожести и саму фразу.
        """
        normalized_text = normalize_text(text)
        if not normalized_text:
            return 0, None

        top_phrases = await self._get_top_phrases()
        if not top_phrases:
            return 0, None

        # Используем process для поиска наилучшего совпадения
        # extractOne возвращает кортеж (фраза, схожесть, индекс)
        best_match = fuzz.process.extractOne(
            normalized_text,
            top_phrases,
            scorer=fuzz.partial_ratio,
            score_cutoff=self.config.LEARNING_MIN_RATIO,
        )

        if best_match:
            phrase, score, _ = best_match
            logger.debug(f"Найдено совпадение с фразой '{phrase}' (схожесть: {score:.2f}%)")
            return int(score), ScoredPhrase(phrase, float(score))

        return 0, None

    async def is_bad_domain(self, host: str) -> bool:
        """Проверяет, находится ли домен в черном списке спам-доменов."""
        if not host:
            return False
        try:
            score = await self.redis.zscore(self.keys.spam_domains(), host.lower())
            return (score or 0.0) >= self.config.LEARNING_DOMAIN_MIN_SCORE
        except Exception as e:
            logger.error(f"Ошибка при проверке домена '{host}': {e}")
            return False