# ===============================================================
# Файл: bot/filters/threat_filter.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Комплексная система предотвращения угроз. Заменяет
# простой спам-фильтр на многоуровневый анализ, включающий RBAC,
# поведенческие факторы (частота сообщений), глубокий AI-анализ
# контента на предмет скама и фишинга, а также гибкую систему
# оценки угроз (Threat Score).
# ===============================================================

import time
from typing import Dict, Any, List, Optional, Set

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.services.user_service import UserService, UserProfile
from bot.services.ai_service import AIService, AIVerdict
from bot.config.settings import AppSettings # Предполагается, что настройки здесь
from bot.filters.access_filters import UserRole

# ПРИМЕЧАНИЕ: Этот класс настроек должен быть частью вашего основного
# файла settings.py для централизованного управления.
class ThreatFilterSettings:
    """Настройки для системы предотвращения угроз."""
    # Песочница для новых пользователей (в секундах)
    SANDBOX_PERIOD_SECONDS: int = 86400  # 24 часа
    
    # Пороги токсичности от AI
    CRITICAL_TOXICITY_THRESHOLD: float = 0.90
    HIGH_TOXICITY_THRESHOLD: float = 0.75

    # Настройки анализа частоты сообщений (Velocity Check)
    VELOCITY_CHECK_PERIOD_SECONDS: int = 5 # Интервал для отслеживания
    VELOCITY_CHECK_MESSAGE_LIMIT: int = 4 # Макс. сообщений за интервал

    # Очки для системы оценки угроз (Threat Score)
    # Базовый порог срабатывания
    THREAT_SCORE_THRESHOLD: int = 100
    
    # Штрафы за намерения, определенные AI
    SCORE_ADVERTISEMENT: int = 45
    SCORE_INSULT: int = 50
    SCORE_CRYPTO_SCAM: int = 80 # Высокий приоритет для крипто-скама
    SCORE_HIGH_TOXICITY: int = 40

    # Штрафы за контент
    SCORE_HAS_LINK: int = 25
    SCORE_PER_STOP_WORD: int = 20
    SCORE_FORWARDED_MESSAGE: int = 30
    SCORE_VELOCITY_EXCEEDED: int = 60

    # Модификаторы на основе профиля пользователя
    LOW_TRUST_SCORE_THRESHOLD: int = 50
    LOW_TRUST_SCORE_MULTIPLIER: float = 1.5
    HIGH_TRUST_SCORE_THRESHOLD: int = 100
    # 1 очко скидки за каждые 2 очка доверия сверх порога
    TRUST_DISCOUNT_FACTOR: float = 0.5


class ThreatFilter(BaseFilter):
    """
    Интеллектуальный, многоуровневый фильтр для проактивного обнаружения угроз.
    """
    
    async def __call__(self, message: Message, user_service: UserService, ai_service: AIService, settings: AppSettings) -> bool:
        """
        Основной метод фильтра, вызываемый aiogram.
        
        :param message: Входящее сообщение.
        :param user_service: Сервис для работы с пользователями.
        :param ai_service: Сервис для AI-анализа.
        :param settings: Глобальные настройки приложения.
        :return: True, если сообщение является угрозой и должно быть заблокировано.
        """
        user = message.from_user
        if not user:
            return False # Не обрабатываем события без пользователя

        # Получаем профиль пользователя и настройки фильтра
        user_profile = await user_service.get_or_create_user(user.id, message.chat.id)
        filter_settings = ThreatFilterSettings() # В идеале: settings.threat_filter

        # --- Уровень 0: Проверка на иммунитет ---
        if await self._check_immunity(user_profile.role):
            return False

        # --- Уровень 1: "Умная песочница" для новичков ---
        if await self._check_sandbox(message, user_profile, filter_settings, user_service):
            return True

        # --- Уровень 2: Анализ частоты сообщений (Velocity Check) ---
        is_velocity_exceeded = await self._check_velocity(user_profile, filter_settings, user_service)

        # --- Уровень 3: Глубокий AI-анализ контента ---
        ai_verdict = await ai_service.analyze_message(message.text or message.caption or "")
        if ai_verdict.toxicity_score > filter_settings.CRITICAL_TOXICITY_THRESHOLD:
            await user_service.log_violation(user.id, message.chat.id, "critical_toxicity")
            return True
        
        # --- Уровень 4: Комплексная оценка угрозы (Threat Score) ---
        threat_score, reasons = await self._calculate_threat_score(
            message, user_profile, ai_verdict, is_velocity_exceeded, ai_service, filter_settings
        )

        # --- Финальное решение ---
        if threat_score >= filter_settings.THREAT_SCORE_THRESHOLD:
            await user_service.log_violation(
                user.id, message.chat.id, "threat_score_exceeded",
                details={"score": round(threat_score), "reasons": reasons}
            )
            return True

        return False

    async def _check_immunity(self, role: UserRole) -> bool:
        """Проверяет, обладает ли пользователь иммунитетом (модератор и выше)."""
        return role >= UserRole.MODERATOR

    async def _check_sandbox(self, message: Message, user_profile: UserProfile, settings: ThreatFilterSettings, user_service: UserService) -> bool:
        """Применяет ограничения "песочницы" для новых пользователей."""
        is_new_user = (time.time() - user_profile.join_timestamp) < settings.SANDBOX_PERIOD_SECONDS
        if not is_new_user:
            return False

        # В песочнице блокируем только явные ссылки и пересылку
        has_url_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        is_forwarded = message.forward_from or message.forward_from_chat

        if has_url_links or is_forwarded:
            await user_service.log_violation(user_profile.user_id, message.chat.id, "sandbox_violation")
            return True
        return False

    async def _check_velocity(self, user_profile: UserProfile, settings: ThreatFilterSettings, user_service: UserService) -> bool:
        """Проверяет частоту отправки сообщений пользователем."""
        is_exceeded = await user_service.check_message_velocity(
            user_profile.user_id,
            limit=settings.VELOCITY_CHECK_MESSAGE_LIMIT,
            period=settings.VELOCITY_CHECK_PERIOD_SECONDS
        )
        return is_exceeded

    async def _calculate_threat_score(
        self, message: Message, user_profile: UserProfile, ai_verdict: AIVerdict,
        is_velocity_exceeded: bool, ai_service: AIService, settings: ThreatFilterSettings
    ) -> (float, List[str]):
        """Рассчитывает итоговый балл угрозы на основе всех факторов."""
        score = 0.0
        reasons: List[str] = []

        # 1. Штрафы на основе AI-анализа
        if ai_verdict.intent == "advertisement":
            score += settings.SCORE_ADVERTISEMENT
            reasons.append(f"ai:ad({ai_verdict.confidence:.2f})")
        if ai_verdict.intent == "insult":
            score += settings.SCORE_INSULT
            reasons.append(f"ai:insult({ai_verdict.confidence:.2f})")
        if ai_verdict.intent == "crypto_scam":
            score += settings.SCORE_CRYPTO_SCAM
            reasons.append(f"ai:scam({ai_verdict.confidence:.2f})")
        if ai_verdict.toxicity_score > settings.HIGH_TOXICITY_THRESHOLD:
            score += settings.SCORE_HIGH_TOXICITY
            reasons.append(f"ai:toxic({ai_verdict.toxicity_score:.2f})")

        # 2. Штрафы на основе контента
        if any(e.type in ["url", "text_link"] for e in message.entities or []):
            score += settings.SCORE_HAS_LINK
            reasons.append("content:link")
        if message.forward_from or message.forward_from_chat:
            score += settings.SCORE_FORWARDED_MESSAGE
            reasons.append("content:forward")

        stop_words = await ai_service.get_stop_words()
        found_sw = {word for word in stop_words if word in (message.text or "").lower()}
        if found_sw:
            score += settings.SCORE_PER_STOP_WORD * len(found_sw)
            reasons.append(f"content:stop_words({','.join(found_sw)})")
        
        # 3. Поведенческие штрафы
        if is_velocity_exceeded:
            score += settings.SCORE_VELOCITY_EXCEEDED
            reasons.append("behavior:velocity")

        # 4. Модификаторы на основе профиля пользователя
        if user_profile.trust_score < settings.LOW_TRUST_SCORE_THRESHOLD:
            score *= settings.LOW_TRUST_SCORE_MULTIPLIER
            reasons.append(f"mod:low_trust_x{settings.LOW_TRUST_SCORE_MULTIPLIER}")
        
        if user_profile.trust_score > settings.HIGH_TRUST_SCORE_THRESHOLD:
            discount = (user_profile.trust_score - settings.HIGH_TRUST_SCORE_THRESHOLD) * settings.TRUST_DISCOUNT_FACTOR
            score -= discount
            reasons.append(f"mod:trust_discount_-{discount:.1f}")

        return max(0, score), reasons
