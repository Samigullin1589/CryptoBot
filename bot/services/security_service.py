# =================================================================================
# Файл: bot/services/security_service.py (ВЕРСИЯ "Distinguished Engineer" - АВГУСТ 2025)
# Описание: Сервис, отвечающий за анализ сообщений на угрозы (спам, токсичность).
# ИСПРАВЛЕНИЕ: Полностью переработан для соответствия DI-архитектуре.
# Теперь использует AIContentService для анализа, а не делает прямые запросы.
# Устранены все ошибки импорта и несоответствия сигнатур.
# =================================================================================

import logging
from typing import Dict, Any, TYPE_CHECKING

from async_lru import alru_cache

# Импортируем необходимые компоненты
from bot.config.settings import ThreatFilterConfig
from bot.utils.models import AIVerdict

if TYPE_CHECKING:
    from bot.services.ai_content_service import AIContentService

logger = logging.getLogger(__name__)

class SecurityService:
    """
    Сервис для анализа текста на предмет угроз с использованием AI.
    Делегирует фактический вызов AI специализированному сервису.
    """

    def __init__(self, ai_service: "AIContentService", config: ThreatFilterConfig):
        """
        Инициализирует сервис безопасности.

        :param ai_service: Сервис для взаимодействия с AI-моделями.
        :param config: Конфигурация для фильтра угроз.
        """
        self.ai_service = ai_service
        self.config = config
        logger.info(f"SecurityService инициализирован. Защита {'включена' if self.config.enabled else 'выключена'}.")

    def _get_system_prompt(self) -> str:
        """Создает системный промпт для AI-анализатора безопасности."""
        return (
            "You are a security analysis bot for a Telegram chat about cryptocurrency. "
            "Analyze the following message. Respond with ONLY a valid JSON object. "
            "Do not add any other text or markdown formatting. Your task is to classify "
            "the message's intent and assess its potential threat level."
        )

    def _get_response_schema(self) -> Dict[str, Any]:
        """Определяет JSON-схему для структурированного ответа от AI."""
        return {
            "type": "OBJECT",
            "properties": {
                "intent": {
                    "type": "STRING",
                    "enum": ["advertisement", "scam", "phishing", "insult", "question", "discussion", "other"],
                    "description": "Основное намерение сообщения."
                },
                "toxicity_score": {
                    "type": "NUMBER",
                    "description": "Оценка токсичности от 0.0 (нейтрально) до 1.0 (очень токсично)."
                },
                "is_potential_scam": {
                    "type": "BOOLEAN",
                    "description": "True, если сообщение похоже на мошенничество (airdrop, private sale, 'pump-dump')."
                },
                "is_potential_phishing": {
                    "type": "BOOLEAN",
                    "description": "True, если сообщение содержит подозрительные ссылки или призывы к переходу."
                }
            },
            "required": ["intent", "toxicity_score", "is_potential_scam", "is_potential_phishing"]
        }

    @alru_cache(maxsize=1024, ttl=300)
    async def analyze_message(self, text: str) -> AIVerdict:
        """
        Анализирует текст сообщения для выявления угроз.

        Использует AIContentService для выполнения запроса к Gemini API
        со специализированным промптом и схемой ответа.

        :param text: Текст сообщения для анализа.
        :return: Pydantic-модель AIVerdict с результатами анализа.
        """
        default_verdict = AIVerdict()
        
        # Если защита отключена в конфиге или текст пустой, не тратим ресурсы
        if not self.config.enabled or not text or not text.strip():
            return default_verdict

        user_prompt = f"Проанализируй следующее сообщение: '{text}'"
        
        try:
            verdict_dict = await self.ai_service.get_structured_response(
                system_prompt=self._get_system_prompt(),
                user_prompt=user_prompt,
                response_schema=self._get_response_schema()
            )
            
            if not verdict_dict:
                logger.warning(f"Анализ безопасности не вернул результата для текста: '{text[:50]}...'")
                return default_verdict

            logger.info(f"AI Security Verdict for '{text[:30]}...': {verdict_dict}")
            
            # Валидируем и создаем объект AIVerdict
            return AIVerdict(**verdict_dict)

        except Exception as e:
            # Логируем ошибку, но возвращаем вердикт по-умолчанию, чтобы не сломать логику бота
            logger.error(f"Ошибка при анализе сообщения AI: {e}", exc_info=True)
            return default_verdict