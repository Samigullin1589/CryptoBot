# bot/services/ai/service.py
"""
Главный сервис для работы с AI провайдерами.
"""
import json
from typing import Any, Dict, List, Optional

from loguru import logger

from bot.config.settings import settings
from bot.services.ai.gemini_provider import GeminiProvider
from bot.services.ai.openai_provider import OpenAIProvider
from bot.services.ai.providers.base import BaseAIProvider
from bot.utils.text_utils import clean_json_string


class AIContentService:
    """
    Сервис для работы с различными AI провайдерами.
    
    Поддерживает:
    - OpenAI (GPT)
    - Google Gemini
    
    Реализует failover между провайдерами.
    
    Архитектура:
    ┌──────────────────────────────┐
    │  AIContentService (Фасад)   │
    └──────────────────────────────┘
              ↓
    ┌──────────────────────────────┐
    │    Provider Manager          │
    │  (Список провайдеров)        │
    └──────────────────────────────┘
         ↓           ↓
    ┌──────────┐ ┌──────────┐
    │ OpenAI   │ │ Gemini   │
    │ Provider │ │ Provider │
    └──────────┘ └──────────┘
    """
    
    def __init__(self):
        """Инициализирует AI сервис с доступными провайдерами."""
        self.config = settings.ai
        self.providers: List[BaseAIProvider] = []
        
        # Инициализируем провайдеры
        self._initialize_providers()
        
        # Логируем результат инициализации
        if not self.providers:
            logger.critical(
                "❌ No AI providers initialized. "
                "AI functionality unavailable."
            )
        else:
            provider_names = ", ".join(p.get_name() for p in self.providers)
            logger.success(
                f"✅ AIContentService initialized with providers: {provider_names}"
            )
    
    def _initialize_providers(self) -> None:
        """Инициализирует все доступные AI провайдеры."""
        # Инициализация OpenAI
        self._init_openai_provider()
        
        # Инициализация Gemini
        self._init_gemini_provider()
    
    def _init_openai_provider(self) -> None:
        """Инициализирует OpenAI провайдер."""
        try:
            openai_key = (
                settings.OPENAI_API_KEY.get_secret_value()
                if settings.OPENAI_API_KEY
                else None
            )
            
            if not openai_key:
                logger.debug("⚠️ OpenAI API key not configured")
                return
            
            openai_provider = OpenAIProvider(
                api_key=openai_key,
                model=self.config.openai_model,
                timeout=self.config.request_timeout
            )
            
            if openai_provider.is_available():
                self.providers.append(openai_provider)
                logger.info(f"✅ OpenAI provider initialized: {self.config.openai_model}")
            else:
                logger.warning("⚠️ OpenAI provider not available")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI provider: {e}", exc_info=True)
    
    def _init_gemini_provider(self) -> None:
        """Инициализирует Gemini провайдер."""
        try:
            gemini_key = (
                settings.GEMINI_API_KEY.get_secret_value()
                if settings.GEMINI_API_KEY
                else None
            )
            
            if not gemini_key:
                logger.debug("⚠️ Gemini API key not configured")
                return
            
            gemini_provider = GeminiProvider(
                api_key=gemini_key,
                pro_model=self.config.model_name,
                flash_model=self.config.flash_model_name
            )
            
            if gemini_provider.is_available():
                self.providers.append(gemini_provider)
                logger.info(
                    f"✅ Gemini provider initialized: "
                    f"{self.config.model_name} / {self.config.flash_model_name}"
                )
            else:
                logger.warning("⚠️ Gemini provider not available")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini provider: {e}", exc_info=True)
    
    async def get_text_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Генерирует текстовый ответ от AI.
        
        Пытается использовать провайдеры по порядку до первого успеха.
        
        Args:
            prompt: Запрос пользователя
            system_prompt: Системный промпт (необязательно)
            temperature: Температура генерации (необязательно)
        
        Returns:
            Сгенерированный текст или сообщение об ошибке
        """
        if not self.providers:
            logger.error("❌ No AI providers available")
            return "AI service is not configured. Please contact administrator."
        
        # Используем температуру из конфига если не указана
        temp = temperature if temperature is not None else self.config.default_temperature
        
        # Пробуем каждый провайдер
        for idx, provider in enumerate(self.providers, 1):
            try:
                logger.debug(
                    f"🔄 Attempting text generation with {provider.get_name()} "
                    f"(provider {idx}/{len(self.providers)})"
                )
                
                result = await provider.generate_text(
                    prompt,
                    system_prompt,
                    temperature=temp
                )
                
                logger.info(
                    f"✅ Text response generated by {provider.get_name()} "
                    f"({len(result)} chars)"
                )
                
                return result
            
            except Exception as e:
                logger.warning(
                    f"⚠️ {provider.get_name()} failed (attempt {idx}/{len(self.providers)}): {e}"
                )
                
                # Если это последний провайдер, логируем с уровнем error
                if idx == len(self.providers):
                    logger.error(
                        f"❌ All AI providers failed for text generation",
                        exc_info=True
                    )
                
                continue
        
        # Все провайдеры не сработали
        return "AI service temporarily unavailable. Please try again later."
    
    async def get_structured_response(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Генерирует структурированный JSON ответ от AI.
        
        Args:
            prompt: Запрос с описанием требуемой структуры
            json_schema: Схема ожидаемого JSON
            temperature: Температура генерации
        
        Returns:
            Распарсенный JSON или None при ошибке
        """
        if not self.providers:
            logger.error("❌ No AI providers available")
            return None
        
        temp = temperature if temperature is not None else self.config.default_temperature
        
        for idx, provider in enumerate(self.providers, 1):
            try:
                logger.debug(
                    f"🔄 Attempting JSON generation with {provider.get_name()} "
                    f"(provider {idx}/{len(self.providers)})"
                )
                
                raw_json = await provider.generate_json(
                    prompt,
                    json_schema,
                    temperature=temp
                )
                
                # Очищаем и парсим JSON
                cleaned = clean_json_string(raw_json)
                result = json.loads(cleaned)
                
                logger.info(
                    f"✅ JSON response generated by {provider.get_name()}"
                )
                
                return result
            
            except json.JSONDecodeError as e:
                logger.error(
                    f"❌ JSON decode error from {provider.get_name()}: {e}\n"
                    f"Raw response: {raw_json[:200]}..."
                )
                continue
            
            except Exception as e:
                logger.warning(
                    f"⚠️ {provider.get_name()} failed (attempt {idx}/{len(self.providers)}): {e}"
                )
                
                if idx == len(self.providers):
                    logger.error(
                        "❌ All AI providers failed for JSON generation",
                        exc_info=True
                    )
                
                continue
        
        return None
    
    async def analyze_image(
        self,
        prompt: str,
        image_bytes: bytes,
        extract_schema: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Анализирует изображение с помощью AI (только Gemini).
        
        Args:
            prompt: Запрос для анализа изображения
            image_bytes: Байты изображения
            extract_schema: Добавлять ли схему JSON в промпт
        
        Returns:
            Результат анализа в виде словаря или None
        """
        # Фильтруем только Gemini провайдеры (они поддерживают vision)
        vision_providers = [
            p for p in self.providers
            if isinstance(p, GeminiProvider)
        ]
        
        if not vision_providers:
            logger.warning(
                "⚠️ Image analysis unavailable: No Gemini provider configured"
            )
            return None
        
        # Формируем промпт со схемой
        if extract_schema:
            schema_prompt = self._build_image_analysis_prompt(prompt)
        else:
            schema_prompt = prompt
        
        # Пробуем каждый vision провайдер
        for idx, provider in enumerate(vision_providers, 1):
            try:
                logger.debug(
                    f"🔄 Attempting image analysis with {provider.get_name()} "
                    f"(provider {idx}/{len(vision_providers)})"
                )
                
                raw_json = await provider.analyze_image(
                    schema_prompt,
                    image_bytes
                )
                
                # Парсим результат
                cleaned = clean_json_string(raw_json)
                result = json.loads(cleaned)
                
                logger.info(
                    f"✅ Image analyzed by {provider.get_name()}"
                )
                
                return result
            
            except json.JSONDecodeError as e:
                logger.error(
                    f"❌ JSON decode error in image analysis: {e}\n"
                    f"Raw response: {raw_json[:200]}..."
                )
                continue
            
            except Exception as e:
                logger.error(
                    f"❌ Image analysis failed with {provider.get_name()}: {e}",
                    exc_info=True
                )
                continue
        
        logger.error("❌ All vision providers failed for image analysis")
        return None
    
    @staticmethod
    def _build_image_analysis_prompt(base_prompt: str) -> str:
        """
        Строит промпт для анализа изображения со схемой JSON.
        
        Args:
            base_prompt: Базовый промпт
        
        Returns:
            Промпт со схемой
        """
        schema_description = (
            "\n\nReturn JSON with the following structure:\n"
            "{\n"
            '  "is_spam": boolean,  // true if image contains spam/advertising\n'
            '  "has_qr_code": boolean,  // true if QR code detected\n'
            '  "has_text_url": boolean,  // true if URLs found in text\n'
            '  "extracted_text": string,  // OCR text (max 200 chars)\n'
            '  "description": string,  // brief image description\n'
            '  "confidence": float  // confidence score 0.0-1.0\n'
            "}"
        )
        
        return base_prompt + schema_description
    
    def is_available(self) -> bool:
        """
        Проверяет доступность AI сервиса.
        
        Returns:
            True если есть хотя бы один провайдер
        """
        return len(self.providers) > 0
    
    def get_active_provider(self) -> str:
        """
        Возвращает названия активных провайдеров.
        
        Returns:
            Строка с названиями через " + " или "Unavailable"
        """
        if not self.providers:
            return "Unavailable"
        
        return " + ".join(p.get_name() for p in self.providers)
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику по провайдерам.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "total_providers": len(self.providers),
            "available": self.is_available(),
            "providers": [
                {
                    "name": p.get_name(),
                    "available": p.is_available()
                }
                for p in self.providers
            ]
        }