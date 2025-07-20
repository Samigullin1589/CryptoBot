import time
from typing import Dict, Any

from aiogram.filters import BaseFilter
from aiogram.types import Message

# Предполагается, что у вас есть сервисы, отвечающие за работу с БД и AI.
# Они будут передаваться в фильтр через DI (Dependency Injection).
from bot.services.user_service import UserService
from bot.services.ai_service import AIService 
# (этот сервис нужно будет создать, он будет содержать логику для работы с NLP моделями)

class AlphaSpamFilter(BaseFilter):
    """
    Интеллектуальный фильтр, который анализирует сообщение на нескольких уровнях,
    используя данные о пользователе, AI-анализ контента и поведенческие факторы.
    """
    def __init__(self, user_service: UserService, ai_service: AIService):
        self.user_service = user_service
        self.ai_service = ai_service
        # Порог "токсичности", при превышении которого сообщение блокируется мгновенно
        self.critical_toxicity_threshold = 0.9 
        # Порог доверия, ниже которого применяются более строгие правила
        self.low_trust_threshold = 50 
        # Время в чате (в секундах) для выхода из "песочницы"
        self.sandbox_period = 86400 # 24 часа

    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        chat_id = message.chat.id

        # --- Уровень 0: Проверка на иммунитет ---
        # Получаем профиль пользователя из нашего сервиса
        user_profile = await self.user_service.get_or_create_user(user_id, chat_id)
        
        if user_profile.is_admin or user_profile.has_immunity:
            return False # Это админ или доверенный юзер, пропускаем все проверки

        # --- Уровень 1: "Песочница" для новичков ---
        is_in_sandbox = (time.time() - user_profile.join_timestamp) < self.sandbox_period
        
        if is_in_sandbox:
            # Для новичков запрещены ссылки, форварды и медиа
            has_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
            if has_links or message.forward_from or message.forward_from_chat or message.photo or message.video:
                await self.user_service.log_violation(user_id, "sandbox_violation")
                return True # Нарушение правил песочницы -> БЛОК

        # --- Уровень 2: AI-анализ контента ---
        # Получаем оценку от AI-сервиса
        # В реальности здесь будет вызов к NLP-модели
        ai_verdict = await self.ai_service.analyze_message(message.text or message.caption or "")
        
        # Немедленный блок за высокую токсичность
        if ai_verdict.get("toxicity_score", 0) > self.critical_toxicity_threshold:
            await self.user_service.log_violation(user_id, "high_toxicity")
            return True # Критическая токсичность -> БЛОК

        # --- Уровень 3: Поведенческий анализ и принятие решения ---
        threat_score = 0
        reasons = []

        # Оцениваем намерение, определенное AI
        if ai_verdict.get("intent") == "advertisement":
            threat_score += 60 # Рекламное намерение - сильный флаг
            reasons.append("AI:advertisement")

        if ai_verdict.get("intent") == "insult":
            threat_score += 40
            reasons.append("AI:insult")

        # Проверяем наличие ссылок, но уже не блокируем сразу, а добавляем "очки угрозы"
        has_links = any(entity.type in ["url", "text_link"] for entity in message.entities or [])
        if has_links:
            threat_score += 25
            reasons.append("content:has_link")
        
        # Проверяем наличие стоп-слов, они тоже добавляют очки
        if message.text:
            text_lower = message.text.lower()
            stop_words_found = [word for word in self.ai_service.get_stop_words() if word in text_lower]
            if stop_words_found:
                threat_score += 20 * len(stop_words_found)
                reasons.append(f"content:stop_words_{stop_words_found}")

        # Учитываем репутацию пользователя (Рейтинг доверия)
        # Низкий рейтинг доверия увеличивает итоговую угрозу
        if user_profile.trust_score < self.low_trust_threshold:
            threat_score *= 1.5 # Увеличиваем угрозу на 50% для пользователей с низкой репутацией
            reasons.append(f"user:low_trust_score_{user_profile.trust_score}")

        # --- Финальное решение ---
        # Если итоговый счет угрозы превысил 100, считаем сообщение спамом
        if threat_score >= 100:
            await self.user_service.log_violation(user_id, "threat_score_exceeded", details={"score": threat_score, "reasons": reasons})
            return True # Итоговая оценка угрозы слишком высока -> БЛОК

        # Если все проверки пройдены
        return False
