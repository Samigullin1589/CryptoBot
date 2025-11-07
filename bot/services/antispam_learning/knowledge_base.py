# bot/services/antispam_learning/knowledge_base.py
"""
База знаний о спаме в Redis.
"""
from typing import Iterable, List

from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.keys import KeyFactory


class SpamKnowledgeBase:
    """
    База знаний о спаме в Redis.
    
    Управляет хранением и обновлением информации о:
    - Спам-фразах с частотой встречаемости
    - Спам-доменах с оценками
    - Примерах спама для анализа
    
    Использует Redis Sorted Sets для эффективного хранения и запросов.
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует базу знаний.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.key_factory = KeyFactory()
        self.config = settings.security
        
        # Лимиты хранения
        self.max_phrases = getattr(self.config, 'learning_max_phrases', 10000)
        self.max_domains = getattr(self.config, 'learning_max_domains', 5000)
        self.max_samples = getattr(self.config, 'learning_max_samples', 1000)
        
        logger.debug(
            f"🔧 SpamKnowledgeBase инициализирована "
            f"(phrases: {self.max_phrases}, domains: {self.max_domains}, "
            f"samples: {self.max_samples})"
        )
    
    async def add_phrases(self, phrases: set[str]) -> int:
        """
        Добавляет фразы в базу знаний.
        
        Увеличивает счетчик для существующих фраз и добавляет новые.
        Автоматически удаляет наименее частые фразы при превышении лимита.
        
        Args:
            phrases: Набор фраз для добавления
            
        Returns:
            Количество обработанных фраз
        """
        if not phrases:
            logger.debug("⚠️ Пустой набор фраз для добавления")
            return 0
        
        try:
            pipe = self.redis.pipeline()
            
            key = self.key_factory.spam_phrases()
            
            # Увеличиваем счетчик для каждой фразы
            for phrase in phrases:
                pipe.zincrby(key, 1.0, phrase)
            
            # Удаляем наименее частые при превышении лимита
            # Оставляем только топ N
            pipe.zremrangebyrank(key, 0, -(self.max_phrases + 1))
            
            await pipe.execute()
            
            logger.info(f"✅ Добавлено {len(phrases)} фраз в базу знаний")
            return len(phrases)
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления фраз в базу: {e}", exc_info=True)
            return 0
    
    async def add_domains(self, domains: Iterable[str]) -> int:
        """
        Добавляет домены в базу знаний.
        
        Args:
            domains: Список доменов
            
        Returns:
            Количество обработанных доменов
        """
        domains_list = list(domains)
        
        if not domains_list:
            logger.debug("⚠️ Пустой список доменов для добавления")
            return 0
        
        try:
            pipe = self.redis.pipeline()
            
            key = self.key_factory.spam_domains()
            
            # Увеличиваем счетчик для каждого домена
            for domain in domains_list:
                normalized_domain = domain.lower().strip()
                if normalized_domain:
                    pipe.zincrby(key, 1.0, normalized_domain)
            
            # Удаляем наименее частые при превышении лимита
            pipe.zremrangebyrank(key, 0, -(self.max_domains + 1))
            
            await pipe.execute()
            
            logger.info(f"✅ Добавлено {len(domains_list)} доменов в базу знаний")
            return len(domains_list)
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления доменов в базу: {e}", exc_info=True)
            return 0
    
    async def add_sample(self, text: str) -> bool:
        """
        Сохраняет пример спама для анализа.
        
        Args:
            text: Текст спама (обрезается до 2000 символов)
            
        Returns:
            True если успешно сохранено
        """
        if not text:
            logger.warning("⚠️ Пустой текст для сохранения примера")
            return False
        
        try:
            pipe = self.redis.pipeline()
            
            key = self.key_factory.spam_samples()
            
            # Обрезаем текст и добавляем в начало списка
            truncated_text = text[:2000]
            pipe.lpush(key, truncated_text)
            
            # Ограничиваем размер списка
            pipe.ltrim(key, 0, self.max_samples - 1)
            
            await pipe.execute()
            
            logger.debug(f"✅ Сохранен пример спама ({len(truncated_text)} символов)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения примера спама: {e}", exc_info=True)
            return False
    
    async def get_top_phrases(self, limit: int) -> List[str]:
        """
        Получает топ спам-фраз из базы по частоте.
        
        Args:
            limit: Количество фраз
            
        Returns:
            Список фраз (от наиболее частых к менее частым)
        """
        if limit <= 0:
            logger.warning(f"⚠️ Некорректный лимит: {limit}")
            return []
        
        try:
            key = self.key_factory.spam_phrases()
            
            # Получаем топ N фраз в обратном порядке (от большего к меньшему)
            phrases_bytes = await self.redis.zrevrange(key, 0, limit - 1)
            
            # Декодируем байты в строки
            phrases = [
                phrase.decode("utf-8", "ignore")
                for phrase in phrases_bytes
            ]
            
            logger.debug(f"📊 Получено {len(phrases)} топ-фраз из базы")
            return phrases
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения фраз из базы: {e}", exc_info=True)
            return []
    
    async def get_phrase_score(self, phrase: str) -> float:
        """
        Получает оценку (частоту) конкретной фразы.
        
        Args:
            phrase: Фраза для проверки
            
        Returns:
            Оценка фразы (или 0 если не найдена)
        """
        try:
            key = self.key_factory.spam_phrases()
            score = await self.redis.zscore(key, phrase)
            return score or 0.0
        except Exception as e:
            logger.error(f"❌ Ошибка получения оценки фразы: {e}", exc_info=True)
            return 0.0
    
    async def get_domain_score(self, domain: str) -> float:
        """
        Получает оценку домена из базы.
        
        Args:
            domain: Доменное имя
            
        Returns:
            Оценка домена (или 0 если не найден)
        """
        if not domain:
            return 0.0
        
        try:
            key = self.key_factory.spam_domains()
            normalized_domain = domain.lower().strip()
            
            score = await self.redis.zscore(key, normalized_domain)
            return score or 0.0
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка получения оценки домена '{domain}': {e}",
                exc_info=True
            )
            return 0.0
    
    async def get_phrase_count(self) -> int:
        """Возвращает общее количество фраз в базе."""
        try:
            key = self.key_factory.spam_phrases()
            return await self.redis.zcard(key)
        except Exception as e:
            logger.error(f"❌ Ошибка получения количества фраз: {e}")
            return 0
    
    async def get_domain_count(self) -> int:
        """Возвращает общее количество доменов в базе."""
        try:
            key = self.key_factory.spam_domains()
            return await self.redis.zcard(key)
        except Exception as e:
            logger.error(f"❌ Ошибка получения количества доменов: {e}")
            return 0
    
    async def get_sample_count(self) -> int:
        """Возвращает количество сохраненных примеров."""
        try:
            key = self.key_factory.spam_samples()
            return await self.redis.llen(key)
        except Exception as e:
            logger.error(f"❌ Ошибка получения количества примеров: {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """
        Очищает всю базу знаний (для тестирования).
        
        Returns:
            True если успешно очищено
        """
        try:
            pipe = self.redis.pipeline()
            pipe.delete(self.key_factory.spam_phrases())
            pipe.delete(self.key_factory.spam_domains())
            pipe.delete(self.key_factory.spam_samples())
            await pipe.execute()
            
            logger.warning("🗑️ База знаний полностью очищена")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки базы знаний: {e}", exc_info=True)
            return False