# ===============================================================
# Файл: bot/filters/threat_filter.py (ПРОДАКШН-ВЕРСИЯ 2025 - ИСПРАВЛЕННАЯ)
# Описание: Интеллектуальный фильтр для обнаружения угроз.
# ИСПРАВЛЕНИЕ: Метод __call__ адаптирован для получения зависимостей
#              через DI-контейнер deps.
# ===============================================================

from typing import Union, Dict, Any, List
from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.utils.dependencies import Deps

class ThreatFilter(BaseFilter):
    """
    Анализирует сообщение, вычисляет "балл угрозы" и передает
    результаты в хэндлер, если балл превышает порог.
    """
    async def __call__(
        self,
        message: Message,
        deps: Deps,
    ) -> Union[bool, Dict[str, Any]]:
        
        if not message.text or not message.from_user:
            return False

        # Извлекаем необходимые сервисы и конфиг из контейнера зависимостей
        user_service = deps.user_service
        # stop_word_service = deps.stop_word_service # Раскомментируйте, когда сервис будет готов
        config = deps.settings.threat_filter

        user_profile, _ = await user_service.get_or_create_user(message.from_user)
        
        total_score = 0
        reasons: List[str] = []

        # В будущем здесь будет логика со стоп-словами и другими проверками
        # # 1. Проверка на стоп-слова
        # found_stop_words = await stop_word_service.find_stop_words(message.text)
        # if found_stop_words:
        #     reasons.append(f"Стоп-слова: {', '.join(found_stop_words)}")
        #     total_score += config.scores.get("stop_word", 0)

        # 2. Проверка на наличие ссылок
        if message.entities and any(e.type in ["url", "text_link"] for e in message.entities):
            reasons.append("Наличие ссылки")
            # total_score += config.scores.get("has_link", 0) # Раскомментируйте с конфигом
            total_score += 10 # Временное значение для теста

        # 3. Проверка на пересылку сообщения
        if message.forward_date:
            reasons.append("Пересланное сообщение")
            # total_score += config.scores.get("forwarded", 0) # Раскомментируйте с конфигом
            total_score += 5 # Временное значение для теста

        # Если итоговый балл превышает порог, передаем данные в хэндлер
        # min_trigger_score = config.min_trigger_score
        min_trigger_score = 1 # Временное значение для теста
        if total_score >= min_trigger_score:
            return {"threat_score": total_score, "reasons": reasons}
        
        return False