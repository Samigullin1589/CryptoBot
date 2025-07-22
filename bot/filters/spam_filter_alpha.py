import time
from typing import Dict, Any

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.services.user_service import UserService
from bot.services.ai_service import AIService 

class AlphaSpamFilter(BaseFilter):
    """
    Интеллектуальный фильтр, который анализирует сообщение на нескольких уровнях,
    используя данные о пользователе, AI-анализ контента и поведенческие факторы.
    Версия с тонкой настройкой для уменьшения ложных срабатываний.
    """
    def __init__(self, user_service: UserService, ai_service: AIService):
        self.user_service = user_service
        self.ai_service = ai_service
        self.critical_toxicity_threshold = 0.9 
        self.low_trust_threshold = 50
        # --- ИЗМЕНЕНИЕ: Увеличиваем песочницу до 1 дня, но делаем ее мягче ---
        self.sandbox_period = 86400 # 24 часа
        # -----------------------------------------------------------------

    async def __call__(self, message: Message, user_service: UserService, ai_service: AIService) -> bool:
        self.user_service = user_service
        self.ai_service = ai_service
        
        user_id = message.from_user.id
        chat_id = message.chat.id

        # --- Уровень 0: Проверка на иммунитет ---
        user_profile = await self.user_service.get_or_create_user(user_id, chat_id)
        
        if user_profile.is_admin or user_profile.has_immunity:
            return False

        # --- Уровень 1: "Умная песочница" ---
        is_in_sandbox = (time.time() - user_profile.join_timestamp) < self.sandbox_period
        
        if is_in_sandbox:
            # --- ИЗМЕНЕНИЕ: Песочница теперь блокирует только явные URL-ссылки и пересылку ---
            # Номера телефонов, фото и обычные сообщения теперь разрешены.
            has_url_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
            if has_url_links or message.forward_from or message.forward_from_chat:
                await self.user_service.log_violation(user_id, chat_id, "sandbox_violation (URL/Forward)")
                return True
            # ---------------------------------------------------------------------------------

        # --- Уровень 2: AI-анализ контента ---
        ai_verdict = await self.ai_service.analyze_message(message.text or message.caption or "")
        
        if ai_verdict.get("toxicity_score", 0) > self.critical_toxicity_threshold:
            await self.user_service.log_violation(user_id, chat_id, "high_toxicity")
            return True

        # --- Уровень 3: Поведенческий анализ с "системой скидок" ---
        threat_score = 0
        reasons = []

        # --- ИЗМЕНЕНИЕ: Снижаем "штраф" за рекламу ---
        if ai_verdict.get("intent") == "advertisement" or ai_verdict.get("is_potential_spam"):
            threat_score += 45 # Было 60
            reasons.append("AI:advertisement")
        # -------------------------------------------

        if ai_verdict.get("intent") == "insult":
            threat_score += 50
            reasons.append("AI:insult")

        has_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        if has_links:
            threat_score += 30
            reasons.append("content:has_link")
        
        if message.text:
            text_lower = message.text.lower()
            stop_words = await self.ai_service.get_stop_words()
            stop_words_found = [word for word in stop_words if word in text_lower]
            if stop_words_found:
                threat_score += 25 * len(stop_words_found)
                reasons.append(f"content:stop_words_{stop_words_found}")

        # --- ИЗМЕНЕНИЕ: Вводим "скидку за доверие" ---
        # Теперь высокий рейтинг доверия не просто защищает, а активно снижает угрозу.
        if user_profile.trust_score > 100:
            trust_discount = (user_profile.trust_score - 100) * 0.5  # 1 очко скидки за каждые 2 очка доверия
            threat_score -= trust_discount
            reasons.append(f"user:trust_discount_{trust_discount}")
        # ---------------------------------------------

        if user_profile.trust_score < self.low_trust_threshold:
            threat_score *= 1.5
            reasons.append(f"user:low_trust_score_{user_profile.trust_score}")

        # --- Финальное решение ---
        if threat_score >= 100:
            await self.user_service.log_violation(
                user_id, chat_id, "threat_score_exceeded", 
                details={"score": threat_score, "reasons": reasons}
            )
            return True

        return False
