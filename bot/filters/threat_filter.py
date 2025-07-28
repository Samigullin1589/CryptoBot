# ===============================================================
# Файл: bot/filters/threat_filter.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Комплексная система предотвращения угроз (Threat
# Prevention System). Анализирует сообщения на нескольких
# уровнях для защиты чата от вредоносной активности.
# ===============================================================
import time
import logging
from typing import Dict, Any, List

from aiogram.filters import BaseFilter
from aiogram.types import Message

# --- ИСПРАВЛЕНИЕ: Импортируем новые, правильные сервисы и модели ---
from bot.services.user_service import UserService
from bot.services.security_service import SecurityService
from bot.utils.models import UserProfile, AIVerdict, UserRole
from bot.config.settings import AppSettings
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

logger = logging.getLogger(__name__)

class ThreatFilter(BaseFilter):
    """
    Интеллектуальный фильтр, который анализирует сообщение на нескольких уровнях,
    используя данные о пользователе, AI-анализ контента и поведенческие факторы.
    """
    async def __call__(
        self, 
        message: Message, 
        user_service: UserService, 
        security_service: SecurityService, # Используем новый сервис
        settings: AppSettings
    ) -> bool:
        """
        Главный метод фильтра. Вызывается для каждого сообщения.
        Возвращает True, если сообщение должно быть заблокировано.
        """
        # Фильтр работает только с текстовыми сообщениями или сообщениями с подписями
        if not (message.text or message.caption):
            return False

        user_profile = await user_service.get_user_profile(message.from_user.id)
        
        # --- Уровень 0: Проверка на иммунитет ---
        if self._check_immunity(user_profile):
            return False

        # --- Уровень 1: "Умная песочница" для новичков ---
        if self._check_sandbox(message, user_profile, settings.threat_filter):
            await user_service.log_violation(
                user_id=user_profile.user_id,
                reason="sandbox_violation",
                details={"message_type": "link_or_forward"}
            )
            return True

        # --- Уровень 2: AI-анализ контента ---
        ai_verdict = await security_service.analyze_message(message.text or message.caption or "")
        if self._check_critical_threats(ai_verdict, settings.threat_filter):
            await user_service.log_violation(
                user_id=user_profile.user_id,
                reason="critical_ai_threat",
                details=ai_verdict.model_dump()
            )
            return True

        # --- Уровень 3: Поведенческий анализ на основе очков угрозы ---
        threat_score, reasons = await self._calculate_threat_score(
            message, user_profile, ai_verdict, security_service, settings.threat_filter
        )
        
        # --- Финальное решение ---
        if threat_score >= settings.threat_filter.threat_score_threshold:
            await user_service.log_violation(
                user_id=user_profile.user_id,
                reason="threat_score_exceeded",
                details={"score": threat_score, "reasons": reasons, "verdict": ai_verdict.model_dump()}
            )
            return True

        return False

    def _check_immunity(self, user_profile: UserProfile) -> bool:
        """Проверяет, имеет ли пользователь иммунитет к проверкам."""
        return user_profile.role >= UserRole.MODERATOR

    def _check_sandbox(self, message: Message, user_profile: UserProfile, config: AppSettings.ThreatFilterSettings) -> bool:
        """Проверяет, находится ли пользователь в "песочнице" и нарушает ли ее правила."""
        is_in_sandbox = (time.time() - user_profile.join_timestamp) < config.sandbox_period_seconds
        if not is_in_sandbox:
            return False
        
        has_url_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        return has_url_links or message.forward_from or message.forward_from_chat

    def _check_critical_threats(self, ai_verdict: AIVerdict, config: AppSettings.ThreatFilterSettings) -> bool:
        """Проверяет наличие критических угроз по вердикту AI."""
        if ai_verdict.toxicity_score > config.critical_toxicity_threshold:
            return True
        if ai_verdict.threat_category in ["SCAM", "PHISHING"]:
            return True
        return False

    async def _calculate_threat_score(
        self, message: Message, user_profile: UserProfile, ai_verdict: AIVerdict,
        security_service: SecurityService, config: AppSettings.ThreatFilterSettings
    ) -> tuple[float, list[str]]:
        """Рассчитывает итоговый балл угрозы на основе множества факторов."""
        threat_score = 0.0
        reasons = []

        # Начисление очков по вердикту AI
        if ai_verdict.is_spam:
            threat_score += config.score_weights.ai_spam
            reasons.append("ai:spam")
        
        # Начисление очков за контент
        has_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        if has_links:
            threat_score += config.score_weights.has_link
            reasons.append("content:has_link")

        # Модификаторы на основе профиля пользователя
        if user_profile.trust_score < config.low_trust_threshold:
            threat_score *= config.multipliers.low_trust
            reasons.append(f"user:low_trust_multiplier")
        
        # Скидка за высокий рейтинг доверия
        if user_profile.trust_score > config.high_trust_threshold:
            trust_discount = (user_profile.trust_score - config.high_trust_threshold) * config.multipliers.high_trust_discount_factor
            threat_score -= trust_discount
            reasons.append(f"user:trust_discount")

        return max(0, threat_score), reasons
