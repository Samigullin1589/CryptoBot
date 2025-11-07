# bot/services/advanced_security/service.py
"""
Главный сервис продвинутой системы безопасности.
"""
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.advanced_security.config import SecurityConfig
from bot.services.advanced_security.inspectors import (
    DomainInspector,
    ImageInspector,
    PhraseInspector,
    TextInspector,
)
from bot.services.advanced_security.models import InspectionResult
from bot.services.advanced_security.verdict_calculator import VerdictCalculator
from bot.utils.models import SecurityVerdict


class AdvancedSecurityService:
    """
    Продвинутая система безопасности для борьбы со спамом.
    
    Архитектура:
    ┌─────────────────────────────────────┐
    │  AdvancedSecurityService (Фасад)   │
    └─────────────────────────────────────┘
               ↓
    ┌──────────────────────────────────────┐
    │         Inspectors (Модульные)       │
    ├──────────────────────────────────────┤
    │ • TextInspector                      │
    │ • DomainInspector                    │
    │ • PhraseInspector (Learning)         │
    │ • ImageInspector (Vision)            │
    └──────────────────────────────────────┘
               ↓
    ┌──────────────────────────────────────┐
    │      VerdictCalculator               │
    │   (Оценка + Страйки → Действие)     │
    └──────────────────────────────────────┘
    
    Функции:
    - Многоуровневый анализ сообщений
    - Самообучающаяся система (через learning service)
    - Система страйков с автобаном
    - Анализ изображений (опционально)
    - Детальное логирование и метрики
    """
    
    def __init__(
        self,
        redis: Redis,
        learning_service,
        vision_service: Optional[any] = None,
        config: Optional[SecurityConfig] = None
    ):
        """
        Инициализирует сервис безопасности.
        
        Args:
            redis: Клиент Redis для страйков
            learning_service: Сервис обучения (AntiSpamLearningService)
            vision_service: Опциональный сервис анализа изображений
            config: Опциональная конфигурация (по умолчанию из settings)
        """
        self.redis = redis
        self.learning_service = learning_service
        self.vision_service = vision_service
        
        # Загружаем конфигурацию
        self.config = config or self._load_config()
        
        # Инициализируем инспекторы
        self._init_inspectors()
        
        # Инициализируем калькулятор вердиктов
        self.verdict_calculator = VerdictCalculator(self.redis, self.config)
        
        logger.success("✅ Сервис AdvancedSecurityService инициализирован")
    
    def _load_config(self) -> SecurityConfig:
        """Загружает конфигурацию из settings."""
        threat_config = settings.THREAT_FILTER
        
        return SecurityConfig(
            SCORE_DELETE=getattr(threat_config, 'SCORE_DELETE', 15),
            SCORE_WARN=getattr(threat_config, 'SCORE_WARN', 30),
            SCORE_MUTE=getattr(threat_config, 'SCORE_MUTE', 50),
            SCORE_BAN=getattr(threat_config, 'SCORE_BAN', 70),
            HEURISTIC_WORD_SCORE=getattr(threat_config, 'HEURISTIC_WORD_SCORE', 20),
            HEURISTIC_INVITE_SCORE=getattr(threat_config, 'HEURISTIC_INVITE_SCORE', 25),
            HEURISTIC_LENGTH_SCORE=getattr(threat_config, 'HEURISTIC_LENGTH_SCORE', 10),
            BAD_DOMAIN_SCORE=getattr(threat_config, 'BAD_DOMAIN_SCORE', 40),
            SUSPICIOUS_TLD_SCORE=getattr(threat_config, 'SUSPICIOUS_TLD_SCORE', 15),
            IMAGE_SPAM_SCORE=getattr(threat_config, 'IMAGE_SPAM_SCORE', 35),
            MAX_TEXT_LENGTH=getattr(threat_config, 'MAX_TEXT_LENGTH', 2000),
            STRIKES_FOR_AUTOBAN=getattr(threat_config, 'STRIKES_FOR_AUTOBAN', 3),
            REPEAT_WINDOW_SECONDS=getattr(threat_config, 'REPEAT_WINDOW_SECONDS', 3600),
            SUSPICIOUS_WORDS=getattr(threat_config, 'SUSPICIOUS_WORDS', None),
            SUSPICIOUS_TLDS=getattr(threat_config, 'SUSPICIOUS_TLDS', None),
            SAFE_DOMAINS=getattr(threat_config, 'SAFE_DOMAINS', None),
        )
    
    def _init_inspectors(self) -> None:
        """Инициализирует все инспекторы."""
        self.text_inspector = TextInspector(self.config)
        
        self.domain_inspector = DomainInspector(
            self.config,
            self.learning_service
        )
        
        self.phrase_inspector = PhraseInspector(
            self.config,
            self.learning_service
        )
        
        self.image_inspector = ImageInspector(
            self.config,
            self.vision_service
        )
        
        logger.debug("✅ Инспекторы инициализированы")
    
    async def inspect_message(
        self,
        message: Message,
        bot: Optional[Bot] = None
    ) -> SecurityVerdict:
        """
        Выполняет комплексную проверку сообщения.
        
        Проводит анализ по всем инспекторам, объединяет результаты
        и вычисляет финальный вердикт.
        
        Args:
            message: Сообщение для проверки
            bot: Экземпляр бота (для анализа изображений)
            
        Returns:
            Вердикт с действием и причинами
        """
        user = message.from_user
        
        if not user:
            logger.warning("Сообщение без пользователя, пропуск проверки")
            return SecurityVerdict()
        
        # Извлекаем текст
        text = (message.text or message.caption or "").strip()
        
        # Объединенный результат всех проверок
        combined_result = InspectionResult()
        
        # Запускаем инспекторы последовательно
        try:
            # 1. Анализ текста
            text_result = await self.text_inspector.inspect(text)
            combined_result.merge(text_result)
            
            # 2. Анализ доменов
            domain_result = await self.domain_inspector.inspect(text)
            combined_result.merge(domain_result)
            
            # 3. Анализ по базе знаний
            phrase_result = await self.phrase_inspector.inspect(text)
            combined_result.merge(phrase_result)
            
            # 4. Анализ изображений (если есть бот)
            if bot:
                image_result = await self.image_inspector.inspect(message, bot)
                combined_result.merge(image_result)
        
        except Exception as e:
            logger.error(f"Ошибка при проверке сообщения: {e}", exc_info=True)
        
        # Вычисляем финальный вердикт
        action, reason = await self.verdict_calculator.calculate(
            combined_result.score,
            message.chat.id,
            user.id
        )
        
        # Формируем итоговый вердикт
        verdict = SecurityVerdict(
            score=combined_result.score,
            action=action,
            reason=reason,
            details=combined_result.reasons,
            domains=combined_result.metadata.get("domains", [])
        )
        
        # Логируем если есть действие
        if verdict.action:
            logger.warning(
                f"🚨 Обнаружена угроза от user_id={user.id} в chat_id={message.chat.id}: "
                f"action={verdict.action}, score={verdict.score}, "
                f"reasons={verdict.details}"
            )
        
        return verdict
    
    async def get_user_strikes(self, chat_id: int, user_id: int) -> int:
        """Получает количество страйков пользователя."""
        return await self.verdict_calculator.get_user_strikes(chat_id, user_id)
    
    async def reset_user_strikes(self, chat_id: int, user_id: int) -> bool:
        """Сбрасывает страйки пользователя."""
        return await self.verdict_calculator.reset_user_strikes(chat_id, user_id)