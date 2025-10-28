# =================================================================================
# bot/services/ai_content_service.py
# Версия: ИСПРАВЛЕННАЯ (27.10.2025) - Distinguished Engineer
# Описание:
#   • ИСПРАВЛЕНО: settings.AI → settings.ai
#   • ИСПРАВЛЕНО: settings.GOOGLE_API_KEY → settings.GEMINI_API_KEY
#   • ИСПРАВЛЕНО: self.config.GEMINI_PRO_MODEL → self.config.model_name
#   • ИСПРАВЛЕНО: self.config.GEMINI_FLASH_MODEL → self.config.flash_model_name
#   • ИСПРАВЛЕНО: self.config.OPENAI_MODEL → self.config.openai_model
#   • ИСПРАВЛЕНО: self.config.REQUEST_TIMEOUT → self.config.request_timeout
#   • ИСПРАВЛЕНО: self.config.DEFAULT_TEMPERATURE → self.config.default_temperature
#   • ИСПРАВЛЕНО: from loguru import logger → import logging
# =================================================================================

import asyncio
import base64
import json
import logging  # ✅ ИСПРАВЛЕНО: Заменен import loguru на стандартный logging
from typing import Any, Dict, List, Optional, Sequence, Union

import backoff

# --- Импорты провайдеров AI ---
try:
    from openai import APIConnectionError, OpenAI, RateLimitError
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    APIConnectionError = RateLimitError = Exception
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    google_exceptions = None
    GenerationConfig = object
    GEMINI_AVAILABLE = False

from bot.config.settings import settings
from bot.utils.text_utils import clean_json_string, clip_text

logger = logging.getLogger(__name__)  # ✅ ИСПРАВЛЕНО: Стандартный logger


class AIContentService:
    """
    Абстракция для работы с различными LLM-провайдерами.
    - Использует OpenAI, если доступен ключ.
    - Автоматически переключается на Gemini при ошибках OpenAI.
    - Предоставляет функции для генерации текста, JSON и анализа изображений.
    """

    def __init__(self):
        """Инициализирует клиентов AI на основе доступных ключей в настройках."""
        self.config = settings.ai  # ✅ ИСПРАВЛЕНО: settings.AI → settings.ai
        self.oai_client: Optional[OpenAI] = None
        self.gemini_pro = None
        self.gemini_flash = None

        # --- Инициализация OpenAI ---
        openai_api_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
        if OPENAI_AVAILABLE and openai_api_key:
            try:
                self.oai_client = OpenAI(
                    api_key=openai_api_key, 
                    timeout=self.config.request_timeout  # ✅ ИСПРАВЛЕНО: REQUEST_TIMEOUT → request_timeout
                )
                logger.info(f"AIContentService: OpenAI-клиент инициализирован (модель: {self.config.openai_model}).")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать OpenAI-клиент: {e}")
                self.oai_client = None
        else:
            logger.info("AIContentService: OpenAI-клиент не будет использоваться (ключ не найден или библиотека не установлена).")

        # --- Инициализация Google Gemini ---
        # ✅ ИСПРАВЛЕНО: settings.GOOGLE_API_KEY → settings.GEMINI_API_KEY
        gemini_api_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
        if GEMINI_AVAILABLE and gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                # Настройка безопасности для избежания блокировок на безобидных запросах
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                # ✅ ИСПРАВЛЕНО: GEMINI_PRO_MODEL → model_name, GEMINI_FLASH_MODEL → flash_model_name
                self.gemini_pro = genai.GenerativeModel(self.config.model_name, safety_settings=safety_settings)
                self.gemini_flash = genai.GenerativeModel(self.config.flash_model_name, safety_settings=safety_settings)
                logger.info(
                    f"AIContentService: Gemini-клиент инициализирован (Pro: {self.config.model_name}, Flash: {self.config.flash_model_name})."
                )
            except Exception as e:
                logger.error(f"Не удалось инициализировать Gemini-клиент: {e}")
        else:
            logger.info("AIContentService: Gemini-клиент не будет использоваться (ключ не найден или библиотека не установлена).")

        if not self.oai_client and not self.gemini_pro:
            logger.critical("Ни один AI-провайдер не был инициализирован. Функционал AI будет недоступен.")

    @backoff.on_exception(backoff.expo, (APIConnectionError, RateLimitError), max_tries=3)
    async def _oai_request(self, messages: List[Dict[str, str]], is_json: bool) -> str:
        """Выполняет запрос к OpenAI с обработкой ошибок и повторными попытками."""
        if not self.oai_client:
            raise RuntimeError("OpenAI-клиент не инициализирован.")
        
        request_params = {
            "model": self.config.openai_model,  # ✅ ИСПРАВЛЕНО: OPENAI_MODEL → openai_model
            "messages": messages,
            "temperature": 0.1 if is_json else self.config.default_temperature,  # ✅ ИСПРАВЛЕНО: DEFAULT_TEMPERATURE → default_temperature
        }
        if is_json:
            request_params["response_format"] = {"type": "json_object"}

        response = await asyncio.to_thread(
            self.oai_client.chat.completions.create, **request_params
        )
        return (response.choices[0].message.content or "").strip()

    @backoff.on_exception(backoff.expo, (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable), max_tries=3)
    async def _gemini_request(self, model, contents: Any, is_json: bool) -> str:
        """Выполняет запрос к Gemini с обработкой ошибок и повторными попытками."""
        if not model:
            raise RuntimeError("Модель Gemini не инициализирована.")
            
        gen_config = GenerationConfig(
            temperature=0.1 if is_json else self.config.default_temperature,  # ✅ ИСПРАВЛЕНО
            response_mime_type="application/json" if is_json else "text/plain",
        )
        response = await model.generate_content_async(contents=contents, generation_config=gen_config)
        return response.text.strip()

    async def get_text_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Генерирует текстовый ответ, используя сначала OpenAI, затем Gemini в качестве резерва.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": clip_text(prompt, 8000)})

        if self.oai_client:
            try:
                return await self._oai_request(messages, is_json=False)
            except Exception as e:
                logger.warning(f"Ошибка OpenAI при генерации текста, переключение на Gemini: {e}")

        if self.gemini_pro:
            try:
                # Для Gemini объединяем системный и пользовательский промпты
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                return await self._gemini_request(self.gemini_pro, full_prompt, is_json=False)
            except Exception as e:
                logger.error(f"Ошибка Gemini при генерации текста: {e}")
        
        return "К сожалению, сервис AI временно недоступен."

    async def get_structured_response(self, prompt: str, json_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Генерирует ответ в формате JSON по заданной схеме.
        """
        system_prompt = (
            "Ты должен ответить в формате JSON, который строго соответствует предоставленной схеме. "
            "Не добавляй никаких пояснений, комментариев или markdown-разметки."
            f"Примерная структура JSON: {json.dumps(json_schema, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        raw_json = ""
        if self.oai_client:
            try:
                raw_json = await self._oai_request(messages, is_json=True)
            except Exception as e:
                logger.warning(f"Ошибка OpenAI при генерации JSON, переключение на Gemini: {e}")
                raw_json = ""

        if not raw_json and self.gemini_flash:
            try:
                full_prompt = f"{system_prompt}\n\n{prompt}"
                raw_json = await self._gemini_request(self.gemini_flash, full_prompt, is_json=True)
            except Exception as e:
                logger.error(f"Ошибка Gemini при генерации JSON: {e}")

        if raw_json:
            try:
                return json.loads(clean_json_string(raw_json))
            except json.JSONDecodeError:
                logger.error(f"Не удалось декодировать JSON от AI: {raw_json}")
        
        return None

    async def analyze_image(self, prompt: str, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Анализирует изображение с помощью Gemini Vision и возвращает структурированный JSON.
        """
        if not self.gemini_flash:
            logger.warning("Анализ изображений недоступен: Gemini-клиент не инициализирован.")
            return None

        try:
            image_part = {"mime_type": "image/jpeg", "data": image_bytes}
            schema_prompt = (
                "Проанализируй изображение на основе запроса. "
                "Верни ответ в формате JSON со следующими полями: "
                "'is_spam' (boolean), 'has_qr_code' (boolean), 'has_text_url' (boolean), "
                "'extracted_text' (string, до 200 символов), 'description' (string, краткое описание)."
            )
            full_prompt = f"{prompt}\n\n{schema_prompt}"
            
            raw_json = await self._gemini_request(self.gemini_flash, [full_prompt, image_part], is_json=True)
            if raw_json:
                return json.loads(clean_json_string(raw_json))
        except Exception as e:
            logger.error(f"Ошибка при анализе изображения через Gemini: {e}")
            
        return None