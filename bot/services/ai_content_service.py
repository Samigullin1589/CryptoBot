# ===============================================================
# Файл: bot/services/ai_content_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для взаимодействий с AI, который самостоятельно
# инициализирует SDK и использует декларативные ретраи.
# ИСПРАВЛЕНИЕ: Конструктор полностью переработан для самодостаточности.
# ===============================================================

import logging
import json
from typing import Dict, Any, List, Optional

import backoff
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, ContentDict
from google.api_core import exceptions as google_exceptions

from bot.config.settings import AIConfig
from bot.texts.ai_prompts import get_summary_prompt, get_consultant_prompt

logger = logging.getLogger(__name__)

# Определяем ошибки, при которых стоит повторять запрос
RETRYABLE_EXCEPTIONS = (
    google_exceptions.ResourceExhausted,  # 429 - Квоты исчерпаны
    google_exceptions.ServiceUnavailable, # 503 - Сервис недоступен
    google_exceptions.InternalServerError,  # 500 - Внутренняя ошибка сервера
    google_exceptions.DeadlineExceeded,   # Таймаут
)

class AIContentService:
    """Центральный сервис для генерации контента, построенный на Google AI SDK."""
    
    # ИСПРАВЛЕНО: Конструктор теперь принимает api_key и config,
    # и самостоятельно инициализирует клиент.
    def __init__(self, api_key: str, config: AIConfig):
        """
        Инициализирует сервис и настраивает клиент Google AI.

        :param api_key: API-ключ для Gemini.
        :param config: Конфигурация для AI-сервиса.
        """
        self.config = config
        self.client: Optional[genai.GenerativeModel] = None
        try:
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.config.model_name)
            logger.info(f"Клиент Google AI успешно сконфигурирован для модели {self.config.model_name}.")
        except Exception as e:
            logger.critical(f"Не удалось настроить клиент Google AI: {e}. Все функции AI будут отключены.")

    def _extract_text_from_response(self, response: Any) -> Optional[str]:
        """Безопасно извлекает текстовое содержимое из ответа модели."""
        try:
            return response.candidates[0].content.parts[0].text
        except (AttributeError, IndexError, KeyError):
            # Логируем ошибку, но не выводим весь объект ответа, чтобы избежать спама в логах
            logger.error("Не удалось извлечь текст из ответа AI.")
            return None

    @backoff.on_exception(
        backoff.expo,
        RETRYABLE_EXCEPTIONS,
        max_tries=5, # ИСПРАВЛЕНО: Используем статическое значение вместо лямбды
        on_giveup=lambda details: logger.error(
            f"Запрос к AI не удался после {details['tries']} попыток. Ошибка: {details['exception']}"
        )
    )
    async def _make_request(self, model: genai.GenerativeModel, *args, **kwargs) -> Any:
        """Выполняет асинхронный запрос к SDK и обрабатывает ошибки с помощью backoff."""
        return await model.generate_content_async(*args, **kwargs)

    async def generate_structured_content(
        self, prompt: str, json_schema: Dict
    ) -> Optional[Dict[str, Any]]:
        """Генерирует структурированный JSON."""
        if not self.client: return None

        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=json_schema,
            temperature=self.config.default_temperature
        )
        
        try:
            response = await self._make_request(
                self.client,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                generation_config=generation_config
            )
            json_text = self._extract_text_from_response(response)
            if not json_text: return None
            return json.loads(json_text)
        except json.JSONDecodeError:
            logger.error(f"Не удалось распарсить JSON из ответа AI: {json_text[:200]}...")
            return None
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при генерации структурированного контента: {e}")
            return None

    async def generate_summary(self, text_to_summarize: str) -> Optional[str]:
        """Генерирует краткое саммари, используя быструю Flash модель."""
        if not self.client: return "Не удалось проанализировать."
        
        try:
            flash_model = genai.GenerativeModel(self.config.flash_model_name)
            prompt = get_summary_prompt(text_to_summarize)
            
            response = await self._make_request(flash_model, contents=prompt)
            return self._extract_text_from_response(response)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при генерации саммари: {e}")
            return "Ошибка анализа."


    async def get_consultant_answer(
        self, user_question: str, history: List[ContentDict]
    ) -> Optional[str]:
        """Отвечает на вопрос пользователя в режиме чата."""
        if not self.client: return "AI-консультант временно недоступен."
        
        system_prompt = get_consultant_prompt(user_question)
        full_history = history + [{"role": "user", "parts": [{"text": system_prompt}]}]
        
        try:
            response = await self._make_request(self.client, contents=full_history)
            return self._extract_text_from_response(response)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при ответе консультанта: {e}")
            return "Произошла ошибка, попробуйте позже."
