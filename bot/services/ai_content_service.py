# =================================================================================
# bot/services/ai_content_service.py
# Версия: ИСПРАВЛЕННАЯ (28.10.2025) - Distinguished Engineer
# Описание:
#   • ИСПРАВЛЕНО: AttributeError с google_exceptions
#   • Добавлены заглушки для исключений при отсутствии библиотек
#   • Улучшена обработка ошибок и fallback-логика
#   • Все настройки используют правильные пути (settings.ai.*)
# =================================================================================

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import backoff

# --- Импорты провайдеров AI ---
try:
    from openai import APIConnectionError, OpenAI, RateLimitError
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    # Создаем заглушки для исключений
    class APIConnectionError(Exception):
        pass
    class RateLimitError(Exception):
        pass
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GenerationConfig = object
    HarmCategory = object
    HarmBlockThreshold = object
    GEMINI_AVAILABLE = False
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Создаем заглушки для google_exceptions
    # чтобы декораторы могли использовать их без ошибок AttributeError
    class _GoogleExceptionStub(Exception):
        """Заглушка для Google API исключений когда библиотека не установлена"""
        pass
    
    class _GoogleExceptions:
        """Контейнер заглушек для Google API исключений"""
        ResourceExhausted = _GoogleExceptionStub
        ServiceUnavailable = _GoogleExceptionStub
        GoogleAPIError = _GoogleExceptionStub
    
    google_exceptions = _GoogleExceptions()

from bot.config.settings import settings
from bot.utils.text_utils import clean_json_string, clip_text

logger = logging.getLogger(__name__)


class AIContentService:
    """
    Абстракция для работы с различными LLM-провайдерами.
    - Использует OpenAI, если доступен ключ.
    - Автоматически переключается на Gemini при ошибках OpenAI.
    - Предоставляет функции для генерации текста, JSON и анализа изображений.
    """

    def __init__(self):
        """Инициализирует клиентов AI на основе доступных ключей в настройках."""
        self.config = settings.ai
        self.oai_client: Optional[OpenAI] = None
        self.gemini_pro = None
        self.gemini_flash = None

        # --- Инициализация OpenAI ---
        openai_api_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
        if OPENAI_AVAILABLE and openai_api_key:
            try:
                self.oai_client = OpenAI(
                    api_key=openai_api_key, 
                    timeout=self.config.request_timeout
                )
                logger.info(f"✅ AIContentService: OpenAI инициализирован (модель: {self.config.openai_model})")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инициализировать OpenAI: {e}")
                self.oai_client = None
        else:
            logger.info("ℹ️ OpenAI не будет использоваться (ключ отсутствует или библиотека не установлена)")

        # --- Инициализация Google Gemini ---
        gemini_api_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
        if GEMINI_AVAILABLE and gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                # Настройка безопасности для избежания блокировок
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                self.gemini_pro = genai.GenerativeModel(
                    self.config.model_name, 
                    safety_settings=safety_settings
                )
                self.gemini_flash = genai.GenerativeModel(
                    self.config.flash_model_name, 
                    safety_settings=safety_settings
                )
                logger.info(
                    f"✅ AIContentService: Gemini инициализирован "
                    f"(Pro: {self.config.model_name}, Flash: {self.config.flash_model_name})"
                )
            except Exception as e:
                logger.error(f"❌ Не удалось инициализировать Gemini: {e}")
                self.gemini_pro = None
                self.gemini_flash = None
        else:
            logger.info("ℹ️ Gemini не будет использоваться (ключ отсутствует или библиотека не установлена)")

        if not self.oai_client and not self.gemini_pro:
            logger.critical("❌ Ни один AI-провайдер не инициализирован. Функционал AI недоступен.")

    @backoff.on_exception(
        backoff.expo, 
        (APIConnectionError, RateLimitError), 
        max_tries=3,
        on_backoff=lambda details: logger.warning(f"🔄 Повтор OpenAI запроса (попытка {details['tries']})")
    )
    async def _oai_request(self, messages: List[Dict[str, str]], is_json: bool) -> str:
        """Выполняет запрос к OpenAI с обработкой ошибок и повторными попытками."""
        if not self.oai_client:
            raise RuntimeError("OpenAI-клиент не инициализирован")
        
        request_params = {
            "model": self.config.openai_model,
            "messages": messages,
            "temperature": 0.1 if is_json else self.config.default_temperature,
        }
        if is_json:
            request_params["response_format"] = {"type": "json_object"}

        response = await asyncio.to_thread(
            self.oai_client.chat.completions.create, 
            **request_params
        )
        return (response.choices[0].message.content or "").strip()

    @backoff.on_exception(
        backoff.expo, 
        (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable), 
        max_tries=3,
        on_backoff=lambda details: logger.warning(f"🔄 Повтор Gemini запроса (попытка {details['tries']})")
    )
    async def _gemini_request(self, model, contents: Any, is_json: bool) -> str:
        """Выполняет запрос к Gemini с обработкой ошибок и повторными попытками."""
        if not model:
            raise RuntimeError("Модель Gemini не инициализирована")
            
        gen_config = GenerationConfig(
            temperature=0.1 if is_json else self.config.default_temperature,
            response_mime_type="application/json" if is_json else "text/plain",
        )
        response = await model.generate_content_async(
            contents=contents, 
            generation_config=gen_config
        )
        return response.text.strip()

    async def get_text_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Генерирует текстовый ответ, используя сначала OpenAI, затем Gemini в качестве резерва.
        
        Args:
            prompt: Основной запрос пользователя
            system_prompt: Системный промпт (опционально)
            
        Returns:
            Сгенерированный текстовый ответ
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": clip_text(prompt, 8000)})

        # Попытка 1: OpenAI
        if self.oai_client:
            try:
                result = await self._oai_request(messages, is_json=False)
                logger.debug("✅ Ответ получен от OpenAI")
                return result
            except Exception as e:
                logger.warning(f"⚠️ OpenAI не удалось, переключение на Gemini: {e}")

        # Попытка 2: Gemini (fallback)
        if self.gemini_pro:
            try:
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                result = await self._gemini_request(self.gemini_pro, full_prompt, is_json=False)
                logger.debug("✅ Ответ получен от Gemini")
                return result
            except Exception as e:
                logger.error(f"❌ Gemini также не удалось: {e}")
        
        return "К сожалению, сервис AI временно недоступен. Попробуйте позже."

    async def get_structured_response(
        self, 
        prompt: str, 
        json_schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Генерирует ответ в формате JSON по заданной схеме.
        
        Args:
            prompt: Запрос пользователя
            json_schema: Ожидаемая структура JSON
            
        Returns:
            Структурированный ответ в виде dict или None при ошибке
        """
        system_prompt = (
            "Ты должен ответить в формате JSON, который строго соответствует предоставленной схеме. "
            "Не добавляй никаких пояснений, комментариев или markdown-разметки. "
            f"Примерная структура JSON: {json.dumps(json_schema, ensure_ascii=False, indent=2)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": clip_text(prompt, 7000)}
        ]

        raw_json = ""
        
        # Попытка 1: OpenAI
        if self.oai_client:
            try:
                raw_json = await self._oai_request(messages, is_json=True)
                logger.debug("✅ JSON получен от OpenAI")
            except Exception as e:
                logger.warning(f"⚠️ OpenAI JSON не удался, переключение на Gemini: {e}")

        # Попытка 2: Gemini Flash (быстрее для JSON)
        if not raw_json and self.gemini_flash:
            try:
                full_prompt = f"{system_prompt}\n\n{prompt}"
                raw_json = await self._gemini_request(self.gemini_flash, full_prompt, is_json=True)
                logger.debug("✅ JSON получен от Gemini")
            except Exception as e:
                logger.error(f"❌ Gemini JSON также не удался: {e}")

        # Парсинг JSON
        if raw_json:
            try:
                cleaned = clean_json_string(raw_json)
                result = json.loads(cleaned)
                return result
            except json.JSONDecodeError as e:
                logger.error(f"❌ Не удалось декодировать JSON: {e}\nОтвет AI: {raw_json[:200]}")
        
        return None

    async def analyze_image(
        self, 
        prompt: str, 
        image_bytes: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Анализирует изображение с помощью Gemini Vision и возвращает структурированный JSON.
        
        Args:
            prompt: Запрос для анализа изображения
            image_bytes: Байты изображения
            
        Returns:
            Структурированный анализ изображения или None при ошибке
        """
        if not GEMINI_AVAILABLE or not self.gemini_flash:
            logger.warning("⚠️ Анализ изображений недоступен: Gemini не инициализирован")
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
            
            raw_json = await self._gemini_request(
                self.gemini_flash, 
                [full_prompt, image_part], 
                is_json=True
            )
            
            if raw_json:
                result = json.loads(clean_json_string(raw_json))
                logger.debug("✅ Изображение проанализировано через Gemini")
                return result
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе изображения: {e}")
            
        return None

    def is_available(self) -> bool:
        """Проверяет доступность хотя бы одного AI-провайдера"""
        return bool(self.oai_client or self.gemini_pro)

    def get_active_provider(self) -> str:
        """Возвращает имя активного провайдера"""
        if self.oai_client and self.gemini_pro:
            return "OpenAI + Gemini (fallback)"
        elif self.oai_client:
            return "OpenAI"
        elif self.gemini_pro:
            return "Gemini"
        return "Недоступен"