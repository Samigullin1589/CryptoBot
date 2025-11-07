# bot/services/image_guard/hash_database.py
"""
База данных хэшей спам-изображений в Redis.
"""
from typing import Tuple

from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.image_guard.hasher import ImageHasher
from bot.utils.keys import KeyFactory


class SpamHashDatabase:
    """
    Компонент для работы с базой хэшей спам-изображений в Redis.
    
    Использует bucketing по префиксу хэша для эффективного поиска:
    - Хэш делится на префикс (первые N бит)
    - Каждый bucket содержит хэши с одинаковым префиксом
    - При проверке ищем только в соответствующем bucket
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует базу данных хэшей.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.key_factory = KeyFactory()
        self.config = settings.security
        self.hasher = ImageHasher()
        
        # Загружаем параметры из конфига
        self.prefix_bits = getattr(self.config, 'phash_prefix_bits', 16)
        self.distance_threshold = getattr(self.config, 'phash_distance', 5)
        self.ttl_seconds = getattr(self.config, 'phash_ttl_seconds', 2592000)  # 30 дней
        
        logger.debug(
            f"🔧 SpamHashDatabase инициализирована "
            f"(prefix_bits: {self.prefix_bits}, "
            f"distance_threshold: {self.distance_threshold}, "
            f"ttl: {self.ttl_seconds}s)"
        )
    
    async def is_spam_hash(self, image_hash: int) -> Tuple[bool, str]:
        """
        Проверяет хэш на совпадение с известными спам-хэшами.
        
        Args:
            image_hash: Хэш изображения для проверки
            
        Returns:
            Кортеж (является_спамом, причина)
        """
        try:
            # Вычисляем префикс для bucket
            prefix = image_hash >> (64 - self.prefix_bits)
            bucket_key = self.key_factory.image_hash_bucket(prefix)
            
            # Получаем все хэши из bucket
            candidate_hashes = await self.redis.smembers(bucket_key)
            
            if not candidate_hashes:
                logger.debug(f"✅ Bucket {prefix} пуст, хэш не найден")
                return False, "no_matches"
            
            logger.debug(
                f"🔍 Проверка хэша в bucket {prefix} "
                f"({len(candidate_hashes)} кандидатов)"
            )
            
            # Проверяем каждый кандидат на схожесть
            for ch_bytes in candidate_hashes:
                try:
                    candidate_hash = int(ch_bytes)
                    distance = self.hasher.hamming_distance(image_hash, candidate_hash)
                    
                    logger.debug(
                        f"  - Candidate {candidate_hash}: distance={distance}"
                    )
                    
                    if distance <= self.distance_threshold:
                        similarity = self.hasher.similarity_percent(
                            image_hash, candidate_hash
                        )
                        
                        logger.warning(
                            f"🚨 Найдено совпадение! "
                            f"distance={distance}, similarity={similarity:.1f}%"
                        )
                        
                        return True, f"similar_hash(dist={distance},sim={similarity:.0f}%)"
                
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"⚠️ Некорректный хэш в базе: {ch_bytes} ({e})"
                    )
                    # Удаляем некорректный хэш
                    await self.redis.srem(bucket_key, ch_bytes)
                    continue
            
            logger.debug("✅ Совпадений не найдено")
            return False, "no_similar_hashes"
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка проверки хэша в Redis: {e}",
                exc_info=True
            )
            return False, "redis_error"
    
    async def add_spam_hash(self, image_hash: int) -> bool:
        """
        Добавляет хэш в базу спам-изображений.
        
        Args:
            image_hash: Хэш для добавления
            
        Returns:
            True если успешно добавлено
        """
        try:
            # Вычисляем префикс
            prefix = image_hash >> (64 - self.prefix_bits)
            bucket_key = self.key_factory.image_hash_bucket(prefix)
            
            # Добавляем хэш в bucket с TTL
            pipe = self.redis.pipeline()
            pipe.sadd(bucket_key, str(image_hash))
            pipe.expire(bucket_key, self.ttl_seconds)
            await pipe.execute()
            
            logger.success(
                f"✅ Хэш {image_hash} добавлен в bucket {prefix} "
                f"(TTL: {self.ttl_seconds}s)"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка добавления хэша {image_hash}: {e}",
                exc_info=True
            )
            return False
    
    async def get_bucket_stats(self, prefix: int) -> dict:
        """
        Получает статистику bucket.
        
        Args:
            prefix: Префикс bucket
            
        Returns:
            Словарь со статистикой
        """
        try:
            bucket_key = self.key_factory.image_hash_bucket(prefix)
            
            size = await self.redis.scard(bucket_key)
            ttl = await self.redis.ttl(bucket_key)
            
            return {
                "prefix": prefix,
                "size": size,
                "ttl": ttl,
                "key": bucket_key
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики bucket: {e}")
            return {}
    
    async def clear_bucket(self, prefix: int) -> bool:
        """
        Очищает bucket (для тестирования).
        
        Args:
            prefix: Префикс bucket
            
        Returns:
            True если успешно
        """
        try:
            bucket_key = self.key_factory.image_hash_bucket(prefix)
            await self.redis.delete(bucket_key)
            
            logger.info(f"🗑️ Bucket {prefix} очищен")
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки bucket: {e}")
            return False