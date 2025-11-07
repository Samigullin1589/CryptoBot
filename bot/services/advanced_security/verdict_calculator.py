# bot/services/advanced_security/verdict_calculator.py
"""
Вычисление финального вердикта на основе оценки угрозы.
"""
from typing import Optional, Tuple

from loguru import logger
from redis.asyncio import Redis

from bot.services.advanced_security.config import SecurityConfig
from bot.utils.keys import KeyFactory


class VerdictCalculator:
    """
    Вычисляет финальный вердикт на основе оценки угрозы и истории нарушений.
    
    Определяет необходимое действие:
    - delete: Удаление сообщения
    - warn: Предупреждение
    - mute: Мут пользователя
    - ban: Бан пользователя
    """
    
    def __init__(self, redis: Redis, config: SecurityConfig):
        """
        Инициализация калькулятора вердиктов.
        
        Args:
            redis: Клиент Redis для хранения страйков
            config: Конфигурация безопасности
        """
        self.redis = redis
        self.config = config
        self.key_factory = KeyFactory()
    
    async def calculate(
        self,
        score: int,
        chat_id: int,
        user_id: int
    ) -> Tuple[Optional[str], str]:
        """
        Вычисляет финальное действие на основе оценки и истории.
        
        Args:
            score: Оценка угрозы
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            Кортеж (действие, причина)
        """
        # Определяем базовое действие по оценке
        action, reason = self._get_action_by_score(score)
        
        if not action:
            return None, ""
        
        # Учитываем историю нарушений для усиления действия
        if action in ("delete", "warn", "mute"):
            action, reason = await self._apply_strike_system(
                action, reason, chat_id, user_id
            )
        
        return action, reason
    
    def _get_action_by_score(self, score: int) -> Tuple[Optional[str], str]:
        """
        Определяет действие по оценке угрозы.
        
        Args:
            score: Оценка угрозы
            
        Returns:
            Кортеж (действие, причина)
        """
        if score >= self.config.SCORE_BAN:
            return "ban", f"Критический уровень угрозы (score: {score})"
        
        elif score >= self.config.SCORE_MUTE:
            return "mute", f"Высокий уровень угрозы (score: {score})"
        
        elif score >= self.config.SCORE_WARN:
            return "warn", f"Средний уровень угрозы (score: {score})"
        
        elif score >= self.config.SCORE_DELETE:
            return "delete", f"Низкий уровень угрозы (score: {score})"
        
        return None, ""
    
    async def _apply_strike_system(
        self,
        action: str,
        reason: str,
        chat_id: int,
        user_id: int
    ) -> Tuple[str, str]:
        """
        Применяет систему страйков для усиления действия.
        
        Args:
            action: Текущее действие
            reason: Текущая причина
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            Кортеж (новое действие, новая причина)
        """
        try:
            key = self.key_factory.user_strikes(chat_id, user_id)
            
            # Увеличиваем счетчик страйков
            strikes = await self.redis.incr(key)
            
            # Устанавливаем TTL для автоматического сброса
            await self.redis.expire(key, self.config.REPEAT_WINDOW_SECONDS)
            
            logger.debug(
                f"User {user_id} в чате {chat_id}: "
                f"страйк #{strikes} (окно: {self.config.REPEAT_WINDOW_SECONDS}s)"
            )
            
            # Проверяем достижение лимита для автобана
            if strikes >= self.config.STRIKES_FOR_AUTOBAN:
                return (
                    "ban",
                    f"Автобан после {strikes} нарушений за "
                    f"{self.config.REPEAT_WINDOW_SECONDS // 60} минут"
                )
        
        except Exception as e:
            logger.error(
                f"Ошибка при обновлении страйков для user {user_id} "
                f"в чате {chat_id}: {e}",
                exc_info=True
            )
        
        return action, reason
    
    async def get_user_strikes(self, chat_id: int, user_id: int) -> int:
        """
        Получает количество страйков пользователя.
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            Количество страйков
        """
        try:
            key = self.key_factory.user_strikes(chat_id, user_id)
            value = await self.redis.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Ошибка получения страйков: {e}")
            return 0
    
    async def reset_user_strikes(self, chat_id: int, user_id: int) -> bool:
        """
        Сбрасывает страйки пользователя.
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        try:
            key = self.key_factory.user_strikes(chat_id, user_id)
            await self.redis.delete(key)
            logger.info(f"Страйки сброшены для user {user_id} в чате {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сброса страйков: {e}")
            return False