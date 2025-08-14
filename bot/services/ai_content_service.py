# ===============================================================
# Файл: bot/services/ai_content_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Сервис для Gemini, использующий актуальную версию библиотеки.
# ИСПРАВЛЕНИЕ: Исправлена SyntaxError в инициализации Gemini-клиента.
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
    """Центральный сервис для генерации контента, построенный на Google AI SDK."""

    def __init__(self, api_key: str, config: AIConfig):
        self.config = config
        self.pro_client: Optional[genai.GenerativeModel] = None
        self.flash_client: Optional[genai.GenerativeModel] = None
        
        if not api_key:
            logger.critical("API-ключ для Gemini не предоставлен. AI-сервис будет отключен.")
            return
        try:
            genai.configure(api_key=api_key)
            # ИСПРАВЛЕНО: Устранена SyntaxError
            self.pro_client = genai.GenerativeModel(
                self.config.model_name,
                tools=[genai.Tool.from_Google Search_retrieval(Google Search_retrieval=genai.GoogleSearchRetrieval())]
            )
            self.flash_client = genai.GenerativeModel(self.config.flash_model_name)
            logger.info(f"Клиенты Google AI успешно сконфигурированы для моделей {self.config.model_name} (с поиском) и {self.config.flash_model_name}.")
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
        """Генерирует структурированный JSON, используя быструю модель."""
        if not self.flash_client: return None
        try:
            json_model = genai.GenerativeModel(
                self.config.flash_model_name,
                generation_config=GenerationConfig(response_mime_type="application/json")
            )
            full_prompt = f"{prompt}\n\nОтвет должен строго соответствовать этой JSON-схеме:\n{json.dumps(json_schema, ensure_ascii=False)}"
            response = await self._make_request(json_model, contents=[{"role": "user", "parts": [{"text": full_prompt}]}])
            json_text = self._extract_text_from_response(response)
            if not json_text: return None
            return json.loads(json_text)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при генерации структурированного контента: {e}", exc_info=True)
            return None
    
    async def get_structured_response(self, system_prompt: str, user_prompt: str, response_schema: Dict) -> Optional[Dict[str, Any]]:
        """Универсальный метод для получения JSON ответа от быстрой модели."""
        if not self.flash_client: return None
        return await self.generate_structured_content(f"{system_prompt}\n\n{user_prompt}", response_schema)

    async def generate_summary(self, text_to_summarize: str) -> str:
        """Генерирует краткое саммари, используя быструю Flash модель."""
        if not self.flash_client: return "Не удалось проанализировать."
        try:
            prompt = get_summary_prompt(text_to_summarize)
            response = await self._make_request(self.flash_client, contents=prompt)
            return self._extract_text_from_response(response) or "Не удалось создать саммари."
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при генерации саммари: {e}", exc_info=True)
            return "Ошибка анализа."

    async def get_consultant_answer(
        self, user_question: str, history: List[ContentDict]
    ) -> str:
        """Отвечает на вопрос пользователя, используя продвинутую Pro модель."""
        if not self.pro_client: return "AI-консультант временно недоступен."
        try:
            system_prompt = get_consultant_prompt()
            chat_history = history + [{"role": "user", "parts": [{"text": user_question}]}]
            
            consultant_model = genai.GenerativeModel(self.config.model_name, system_instruction=system_prompt)
            
            response = await self._make_request(consultant_model, contents=chat_history)
            return self._extract_text_from_response(response) or "AI не смог сформировать ответ."
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при ответе консультанта: {e}", exc_info=True)
            return "Произошла внутренняя ошибка. Пожалуйста, попробуйте позже."
            
    async def explain_unlisted_coin(self, coin_ticker: str) -> str:
        """
        Использует Pro модель с поиском Google, чтобы объяснить статус монеты,
        для которой не найдена цена.
        """
        if not self.pro_client: return "AI-консультант временно недоступен."
        try:
            prompt = (
                f"Я не смог найти цену для криптовалюты с тикером '{coin_ticker}'. "
                "Используя поиск Google, кратко (в 2-3 предложениях на русском языке) объясни, что это за проект и почему его цена может быть недоступна. "
                "Возможные причины: проект еще в тестнете, токен еще не запущен, это скам, или он торгуется только на DEX."
            )
            response = await self._make_request(self.pro_client, contents=prompt)
            return self._extract_text_from_response(response) or "AI не смог найти информацию."
        except Exception as e:
            logger.error(f"Ошибка при поиске информации о нелистинговой монете: {e}", exc_info=True)
            return "Произошла ошибка при поиске дополнительной информации."