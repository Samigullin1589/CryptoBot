# bot/services/image_guard/violation_tracker.py
"""
Отслеживание нарушений пользователей.
"""
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.keys import KeyFactory
from bot.utils.models import ImageVerdict


class ViolationTracker:
    """
    Компонент для отслеживания нарушений пользователей.
    
    Реализует систему эскалации наказаний:
    - 1-2 нарушения: удаление сообщения
    - 3+ нарушения: бан пользователя
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует трекер нарушений.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.key_factory = KeyFactory()
        self.config = settings.security
        
        # Загружаем параметры
        self.window_seconds = getattr(self.config, 'window_seconds', 86400)  # 24 часа
        self.ban_threshold = getattr(self.config, 'image_spam_autoban_threshold', 3)
        
        logger.debug(
            f"🔧 ViolationTracker инициализирован "
            f"(window: {self.window_seconds}s, ban_threshold: {self.ban_threshold})"
        )
    
    async def increment_violations(self, user_id: int) -> int:
        """
        Увеличивает счетчик нарушений пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Текущее количество нарушений в окне
        """
        try:
            key = self.key_factory.user_spam_image_count(user_id)
            
            # Увеличиваем счетчик
            violations = await self.redis.incr(key)
            
            # Устанавливаем TTL только при первом нарушении
            if violations == 1:
                await self.redis.expire(key, self.window_seconds)
                logger.info(
                    f"⚠️ Первое нарушение user_id={user_id} "
                    f"(окно: {self.window_seconds}s)"
                )
            else:
                logger.warning(
                    f"⚠️ Нарушение #{violations} для user_id={user_id}"
                )
            
            return violations
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка обновления счетчика для user {user_id}: {e}",
                exc_info=True
            )
            return 1
    
    def get_punishment(self, violations: int, reason: str) -> ImageVerdict:
        """
        Определяет наказание на основе количества нарушений.
        
        Args:
            violations: Количество нарушений
            reason: Причина нарушения
            
        Returns:
            ImageVerdict с решением о наказании
        """
        if violations >= self.ban_threshold:
            verdict = ImageVerdict(
                action="ban",
                reason=f"{reason} (автобан после {violations} нарушений)"
            )
            
            logger.error(
                f"🚫 АВТОБАН: {violations} нарушений (порог: {self.ban_threshold})"
            )
        else:
            verdict = ImageVerdict(
                action="delete",
                reason=f"{reason} (нарушение #{violations}/{self.ban_threshold})"
            )
            
            logger.warning(
                f"🗑️ Удаление: нарушение #{violations}/{self.ban_threshold}"
            )
        
        return verdict
    
    async def get_violations(self, user_id: int) -> int:
        """
        Получает текущее количество нарушений пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество нарушений
        """
        try:
            key = self.key_factory.user_spam_image_count(user_id)
            value = await self.redis.get(key)
            
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Ошибка получения нарушений: {e}")
            return 0
    
    async def reset_violations(self, user_id: int) -> bool:
        """
        Сбрасывает нарушения пользователя (для админов).
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        try:
            key = self.key_factory.user_spam_image_count(user_id)
            await self.redis.delete(key)
            
            logger.info(f"✅ Нарушения сброшены для user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сброса нарушений: {e}")
            return False