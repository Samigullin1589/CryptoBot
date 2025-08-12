# ===============================================================
# Файл: bot/services/ai_content_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Сервис для Gemini, использующий актуальную версию библиотеки
#           и корректно инициализирующий модель без конфликтующих параметров.
# ИСПРАВЛЕНИЕ: Убран параметр 'tools' из конструктора модели для
#              устранения критической ошибки инициализации.
# ===============================================================

import logging
import json
from typing import Dict, Any, List, Optional

import backoff
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, ContentDict
from google.api_core import exceptions as google_exceptions

from bot.config.settings import settings, AIConfig
from bot.texts.ai_prompts import get_summary_prompt, get_consultant_prompt, get_quiz_json_schema

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
        if not api_key:
            logger.critical("API-ключ для Gemini не предоставлен. AI-сервис будет отключен.")
            return
        try:
            genai.configure(api_key=api_key)
            # ИСПРАВЛЕНО: Убран параметр `tools`. Модели 'pro' и 'flash'
            # используют поиск Google автоматически, когда это необходимо.
            # Явная передача этого параметра в данной версии библиотеки вызывает ошибку.
            self.client = genai.GenerativeModel(self.config.model_name)
            
            logger.info(f"Клиент Google AI успешно сконфигурирован для модели {self.config.model_name}.")
        except Exception as e:
            logger.critical(f"Не удалось настроить клиент Google AI: {e}. Все функции AI будут отключены.", exc_info=True)

    def _extract_text_from_response(self, response: Any) -> Optional[str]:
        """Безопасно извлекает текстовое содержимое из ответа модели."""
        try:
            if response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                 logger.warning(f"Ответ AI заблокирован по причине: {response.prompt_feedback.block_reason.name}")
                 return "Ответ был заблокирован политикой безопасности."
            return None
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
            json_model = genai.GenerativeModel(
                self.config.flash_model_name,
                generation_config=GenerationConfig(response_mime_type="application/json")
            )
            full_prompt = f"{prompt}\n\nОтвет должен строго соответствовать этой JSON-схеме:\n{json.dumps(json_schema, ensure_ascii=False)}"

            response = await self._make_request(
                json_model,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
            )
            json_text = self._extract_text_from_response(response)
            if not json_text: return None
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось распарсить JSON из ответа AI: {json_text[:200]}... Ошибка: {e}")
            return None
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при генерации структурированного контента: {e}", exc_info=True)
            return None

    async def get_consultant_answer(
        self, user_question: str, history: List[ContentDict]
    ) -> str:
        """Отвечает на вопрос пользователя, используя поиск в интернете при необходимости."""
        if not self.client: return "AI-консультант временно недоступен."

        system_prompt = get_consultant_prompt()
        chat_history = history + [{"role": "user", "parts": [{"text": user_question}]}]

        try:
            response = await self._make_request(
                self.client,
                contents=chat_history,
                system_instruction=system_prompt,
            )
            return self._extract_text_from_response(response) or "AI не смог сформировать ответ."
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при ответе консультанта: {e}", exc_info=True)
            return "Произошла внутренняя ошибка. Пожалуйста, попробуйте позже."