# ===============================================================
# Файл: bot/filters/threat_filter.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Комплексная система предотвращения угроз (TPS),
# анализирующая сообщения на нескольких уровнях.
# ===============================================================
import time
import logging
from typing import List, Tuple, Optional

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config.settings import AppSettings, ThreatFilterSettings # <-- ИСПРАВЛЕНИЕ: Импортируем оба класса
from bot.utils.models import UserProfile, AIVerdict, UserRole
from bot.services.user_service import UserService
from bot.services.security_service import SecurityService

logger = logging.getLogger(__name__)

class ThreatFilter(BaseFilter):
    """
    Продвинутый, многоуровневый фильтр угроз, интегрированный с AI
    и системой репутации пользователей.
    """
    async def __call__(
        self,
        message: Message,
        user_service: UserService,
        security_service: SecurityService,
        settings: AppSettings
    ) -> bool:
        """
        Главный метод фильтра, вызываемый для каждого сообщения.
        """
        user_id = message.from_user.id
        chat_id = message.chat.id
        config = settings.threat_filter

        # Уровень 0: Проверка на иммунитет
        user_profile = await user_service.get_user_profile(user_id, chat_id)
        if self._check_immunity(user_profile):
            return False

        # Уровень 1: "Умная песочница"
        if self._check_sandbox(message, user_profile, config):
            await user_service.log_violation(user_id, chat_id, "sandbox_violation")
            return True

        # Уровень 2: AI-анализ контента
        ai_verdict = await self._check_ai_analysis(message, security_service, config)
        if ai_verdict and ai_verdict.toxicity_score > config.critical_toxicity_threshold:
            await user_service.log_violation(user_id, chat_id, "high_toxicity")
            return True

        # Уровень 3: Поведенческий анализ и система очков
        if ai_verdict:
            threat_score, reasons = await self._calculate_threat_score(message, user_profile, ai_verdict, security_service, config)
            if threat_score >= config.threat_score_threshold:
                await user_service.log_violation(
                    user_id, chat_id, "threat_score_exceeded",
                    details={"score": threat_score, "reasons": reasons}
                )
                return True

        return False

    def _check_immunity(self, user_profile: UserProfile) -> bool:
        """Проверяет, есть ли у пользователя иммунитет к проверкам."""
        return user_profile.role >= UserRole.MODERATOR

    # <-- ИСПРАВЛЕНИЕ: Заменен AppSettings.ThreatFilterSettings на ThreatFilterSettings
    def _check_sandbox(self, message: Message, user_profile: UserProfile, config: ThreatFilterSettings) -> bool:
        """Проверяет, находится ли новый пользователь в "песочнице"."""
        is_in_sandbox = (time.time() - user_profile.join_timestamp) < config.sandbox_period_seconds
        if not is_in_sandbox:
            return False

        has_url_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        if has_url_links or message.forward_from or message.forward_from_chat:
            return True
        return False

    # <-- ИСПРАВЛЕНИЕ: Заменен AppSettings.ThreatFilterSettings на ThreatFilterSettings
    async def _check_ai_analysis(self, message: Message, security_service: SecurityService, config: ThreatFilterSettings) -> Optional[AIVerdict]:
        """Запускает AI-анализ, если он необходим."""
        text_content = message.text or message.caption
        if not text_content:
            return None
        return await security_service.analyze_message(text_content)

    # <-- ИСПРАВЛЕНИЕ: Заменен AppSettings.ThreatFilterSettings на ThreatFilterSettings
    async def _calculate_threat_score(
        self,
        message: Message,
        user_profile: UserProfile,
        ai_verdict: AIVerdict,
        security_service: SecurityService,
        config: ThreatFilterSettings
    ) -> Tuple[float, List[str]]:
        """Рассчитывает итоговый балл угрозы на основе множества факторов."""
        threat_score = 0.0
        reasons = []

        if ai_verdict.is_spam:
            threat_score += config.score_weights.ai_spam
            reasons.append("AI:spam")

        has_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        if has_links:
            threat_score += config.score_weights.has_link
            reasons.append("content:has_link")

        # Усиливаем или ослабляем угрозу в зависимости от репутации
        if user_profile.trust_score < config.low_trust_threshold:
            threat_score *= config.multipliers.low_trust
            reasons.append(f"user:low_trust_multiplier_{config.multipliers.low_trust}")
        elif user_profile.trust_score > config.high_trust_threshold:
            trust_discount = threat_score * config.multipliers.high_trust_discount_factor
            threat_score -= trust_discount
            reasons.append(f"user:high_trust_discount_{trust_discount:.2f}")

        return threat_score, reasons
