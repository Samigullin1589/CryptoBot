# ===============================================================
# Файл: bot/filters/threat_filter.py (НОВЫЙ ФАЙЛ)
# Описание: Интеллектуальный фильтр для обнаружения угроз.
# ===============================================================

from typing import Union, Dict, Any, List
from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.services.user_service import UserService
from bot.services.stop_word_service import StopWordService
from bot.config.settings import ThreatFilterConfig

class ThreatFilter(BaseFilter):
    """
    Анализирует сообщение, вычисляет "балл угрозы" и передает
    результаты в хэндлер, если балл превышает порог.
    """
    async def __call__(
        self,
        message: Message,
        user_service: UserService,
        stop_word_service: StopWordService,
        config: ThreatFilterConfig,
    ) -> Union[bool, Dict[str, Any]]:
        
        if not message.text or not message.from_user:
            return False

        user_profile = await user_service.get_or_create_user(message.from_user.id, message.chat.id)
        
        total_score = 0
        reasons: List[str] = []

        # 1. Проверка на стоп-слова
        found_stop_words = await stop_word_service.find_stop_words(message.text)
        if found_stop_words:
            reasons.append(f"Стоп-слова: {', '.join(found_stop_words)}")
            total_score += config.scores.get("stop_word", 0)

        # 2. Проверка на наличие ссылок
        if message.entities and any(e.type in ["url", "text_link"] for e in message.entities):
            reasons.append("Наличие ссылки")
            total_score += config.scores.get("has_link", 0)
            
        # 3. Проверка на пересылку сообщения
        if message.forward_date:
            reasons.append("Пересланное сообщение")
            total_score += config.scores.get("forwarded", 0)

        # 4. Модификатор на основе рейтинга доверия
        if user_profile.trust_score < 50: # Используем фиксированный порог для усиления
            reasons.append("Низкий рейтинг доверия")
            total_score *= config.low_trust_multiplier
        
        # Если итоговый балл превышает порог, передаем данные в хэндлер
        if total_score >= config.min_trigger_score:
            return {"threat_score": total_score, "reasons": reasons}
        
        return False