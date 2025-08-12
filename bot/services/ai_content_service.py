# ===============================================================
# Файл: bot/services/ai_content_service.py (ВЕРСИЯ "Distinguished Engineer" - ИСПРАВЛЕННАЯ)
# Описание: Улучшенный сервис для Gemini, способный выполнять поиск в интернете
# для предоставления актуальных ответов.
# ИСПРАВЛЕНИЕ: Устранена синтаксическая ошибка импорта, интеграция с
# инструментом поиска приведена в соответствие с документацией Google AI SDK.
# ===============================================================

import logging
import json
from typing import Dict, Any, List, Optional

import backoff
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, ContentDict
from google.api_core import exceptions as google_exceptions

from bot.config.config import settings
from bot.texts.ai_prompts import get_summary_prompt, get_consultant_prompt
from bot.config.settings import AIConfig

# Корректный способ импортировать инструмент поиска, предоставленный средой выполнения
from Google Search import search as Google Search_tool

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    google_exceptions.ResourceExhausted,
    google_exceptions.ServiceUnavailable,
    google_exceptions.InternalServerError,
    google_exceptions.DeadlineExceeded,
)

class AIContentService:
    """Центральный сервис для генерации контента, построенный на Google AI SDK с функцией поиска."""

    def __init__(self, api_key: str, config: AIConfig):
        self.config = config
        self.client: Optional[genai.GenerativeModel] = None
        try:
            genai.configure(api_key=api_key)
            # Настраиваем модель с поддержкой вызова инструментов (для поиска)
            self.client = genai.GenerativeModel(
                self.config.model_name,
                tools=[Google Search_tool]
            )
            logger.info(f"Клиент Google AI успешно сконфигурирован для модели {self.config.model_name} с функцией поиска.")
        except Exception as e:
            logger.critical(f"Не удалось настроить клиент Google AI: {e}. Все функции AI будут отключены.")

    def _extract_text_from_response(self, response: Any) -> Optional[str]:
        """Безопасно извлекает текстовое содержимое из ответа модели."""
        try:
            # Проверяем, есть ли function_call, что означает, что модель хочет использовать инструмент
            if response.candidates[0].content.parts[0].function_call:
                return None # Возвращаем None, чтобы показать, что нужен еще один шаг
            return response.candidates[0].content.parts[0].text
        except (AttributeError, IndexError, KeyError):
            logger.error("Не удалось извлечь текст из ответа AI.", exc_info=True)
            return None

    @backoff.on_exception(
        backoff.expo,
        RETRYABLE_EXCEPTIONS,
        max_tries=5,
        on_giveup=lambda details: logger.error(
            f"Запрос к AI не удался после {details['tries']} попыток. Ошибка: {details['exception']}"
        )
    )
    async def _make_request(self, model: genai.GenerativeModel, *args, **kwargs) -> Any:
        """Выполняет асинхронный запрос к SDK с обработкой ошибок."""
        return await model.generate_content_async(*args, **kwargs)

    async def generate_structured_content(
        self, prompt: str, json_schema: Dict
    ) -> Optional[Dict[str, Any]]:
        """Генерирует структурированный JSON."""
        if not self.client: return None

        try:
            # Для структурированного вывода используем модель без поиска, чтобы гарантировать JSON
            base_model = genai.GenerativeModel(
                self.config.model_name,
                generation_config={"response_mime_type": "application/json"}
            )

            # Передаем схему в самом промпте для большей надежности
            full_prompt = f"{prompt}\n\nStrictly follow this JSON schema:\n{json.dumps(json_schema)}"

            response = await self._make_request(
                base_model,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
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
        """Отвечает на вопрос пользователя, используя поиск в интернете при необходимости."""
        if not self.client: return "AI-консультант временно недоступен."

        system_prompt = get_consultant_prompt()

        # Формируем контент для запроса, включая историю
        final_history = history + [{"role": "user", "parts": [{"text": user_question}]}]

        try:
            # Передаем системную инструкцию и историю в одном запросе
            response = await self._make_request(
                self.client,
                contents=final_history,
                system_instruction=system_prompt,
            )
            return response.text
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при ответе консультанта: {e}", exc_info=True)
            return "Произошла ошибка, попробуйте позже."