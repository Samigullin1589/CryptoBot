# ===============================================================
# Файл: bot/services/ai_content_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Сервис для взаимодействий с AI, использующий официальный SDK
# и декларативные повторные запросы через 'backoff'.
# ===============================================================

import logging
from typing import Dict, Any, List, Optional

import backoff
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, ContentDict
from google.api_core import exceptions as google_exceptions

from bot.config.settings import AIConfig
from bot.texts.ai_prompts import get_summary_prompt, get_consultant_prompt

logger = logging.getLogger(__name__)

# --- УЛУЧШЕНИЕ: Используем backoff для декларативных ретраев ---
# Определяем ошибки, при которых стоит повторять запрос
RETRYABLE_EXCEPTIONS = (
    google_exceptions.ResourceExhausted,  # 429 - Квоты исчерпаны
    google_exceptions.ServiceUnavailable, # 503 - Сервис недоступен
    google_exceptions.InternalServerError,  # 500 - Внутренняя ошибка сервера
    google_exceptions.DeadlineExceeded,   # Таймаут
)

class AIContentService:
    """Центральный сервис для генерации контента, построенный на Google AI SDK."""
    def __init__(self, gemini_client: Optional[genai.GenerativeModel], config: AIConfig):
        self.client = gemini_client
        self.config = config
        if not self.client:
            logger.critical("Gemini client is not configured. All AI features will be disabled.")

    def _extract_text_from_response(self, response: Any) -> Optional[str]:
        """Безопасно извлекает текстовое содержимое из ответа модели."""
        try:
            return response.candidates[0].content.parts[0].text
        except (AttributeError, IndexError, KeyError) as e:
            logger.error(f"Could not extract text from AI response: {e}. Response: {response}")
            return None

    # --- УЛУЧШЕНИЕ: Декоратор backoff для автоматических ретраев ---
    @backoff.on_exception(
        backoff.expo,
        RETRYABLE_EXCEPTIONS,
        max_tries=lambda: settings.ai.max_retries,
        on_giveup=lambda details: logger.error(
            f"AI request failed after {details['tries']} tries. Giving up. Error: {details['exception']}"
        )
    )
    async def _make_request(self, model: Optional[genai.GenerativeModel], *args, **kwargs) -> Any:
        """Выполняет запрос к SDK и обрабатывает ошибки с помощью backoff."""
        if not model:
            return None
        return await model.generate_content_async(*args, **kwargs)

    async def generate_structured_content(
        self, prompt: str, json_schema: Dict
    ) -> Optional[Dict[str, Any]]:
        """Генерирует структурированный JSON с использованием Pro модели."""
        if not self.client: return None

        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=json_schema,
            temperature=self.config.default_temperature
        )
        response = await self._make_request(
            self.client,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=generation_config
        )
        
        json_text = self._extract_text_from_response(response)
        if not json_text:
            return None
            
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse structured JSON from AI response: {json_text}")
            return None

    async def generate_summary(self, text_to_summarize: str) -> Optional[str]:
        """Генерирует краткое саммари, используя быструю Flash модель."""
        if not self.client: return "Не удалось проанализировать."
        
        # --- УЛУЧШЕНИЕ: Замена модели "на лету" ---
        flash_model = self.client.with_model(self.config.flash_model_name)
        prompt = get_summary_prompt(text_to_summarize)
        
        response = await self._make_request(flash_model, contents=prompt)
        return self._extract_text_from_response(response)

    async def get_consultant_answer(
        self, user_question: str, history: List[ContentDict]
    ) -> Optional[str]:
        """Отвечает на вопрос пользователя в режиме чата."""
        if not self.client: return "AI-консультант временно недоступен."
        
        system_prompt = get_consultant_prompt(user_question)
        # Добавляем системный промпт к текущей истории
        full_history = history + [{"role": "user", "parts": [{"text": system_prompt}]}]
        
        response = await self._make_request(self.client, contents=full_history)
        return self._extract_text_from_response(response)