# bot/services/ai/service.py
import json
import logging
from typing import Any, Dict, Optional

from bot.config.settings import settings
from bot.services.ai.gemini_provider import GeminiProvider
from bot.services.ai.openai_provider import OpenAIProvider
from bot.utils.text_utils import clean_json_string

logger = logging.getLogger(__name__)


class AIContentService:
    def __init__(self):
        self.config = settings.ai
        self.providers = []
        
        openai_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
        if openai_key:
            openai_provider = OpenAIProvider(
                api_key=openai_key,
                model=self.config.openai_model,
                timeout=self.config.request_timeout
            )
            if openai_provider.is_available():
                self.providers.append(openai_provider)
        
        gemini_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
        if gemini_key:
            gemini_provider = GeminiProvider(
                api_key=gemini_key,
                pro_model=self.config.model_name,
                flash_model=self.config.flash_model_name
            )
            if gemini_provider.is_available():
                self.providers.append(gemini_provider)
        
        if not self.providers:
            logger.critical("❌ No AI providers initialized. AI functionality unavailable.")
        else:
            provider_names = ", ".join(p.get_name() for p in self.providers)
            logger.info(f"✅ AIContentService initialized with providers: {provider_names}")

    async def get_text_response(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> str:
        for provider in self.providers:
            try:
                result = await provider.generate_text(
                    prompt,
                    system_prompt,
                    temperature=self.config.default_temperature
                )
                logger.debug(f"✅ Text response from {provider.get_name()}")
                return result
            except Exception as e:
                logger.warning(f"⚠️ {provider.get_name()} failed: {e}")
                continue
        
        return "AI service temporarily unavailable. Please try again later."

    async def get_structured_response(
        self, 
        prompt: str, 
        json_schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        for provider in self.providers:
            try:
                raw_json = await provider.generate_json(prompt, json_schema)
                logger.debug(f"✅ JSON response from {provider.get_name()}")
                
                cleaned = clean_json_string(raw_json)
                result = json.loads(cleaned)
                return result
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error from {provider.get_name()}: {e}")
                continue
            except Exception as e:
                logger.warning(f"⚠️ {provider.get_name()} failed: {e}")
                continue
        
        return None

    async def analyze_image(
        self, 
        prompt: str, 
        image_bytes: bytes
    ) -> Optional[Dict[str, Any]]:
        for provider in self.providers:
            if not isinstance(provider, GeminiProvider):
                continue
            
            try:
                schema_prompt = (
                    f"{prompt}\n\n"
                    "Return JSON with fields: "
                    "'is_spam' (boolean), 'has_qr_code' (boolean), "
                    "'has_text_url' (boolean), 'extracted_text' (string, max 200 chars), "
                    "'description' (string, brief description)."
                )
                
                raw_json = await provider.analyze_image(schema_prompt, image_bytes)
                
                cleaned = clean_json_string(raw_json)
                result = json.loads(cleaned)
                logger.debug("✅ Image analyzed via Gemini")
                return result
            except Exception as e:
                logger.error(f"❌ Image analysis failed: {e}")
                continue
        
        logger.warning("⚠️ Image analysis unavailable: No Gemini provider")
        return None

    def is_available(self) -> bool:
        return len(self.providers) > 0

    def get_active_provider(self) -> str:
        if not self.providers:
            return "Unavailable"
        
        return " + ".join(p.get_name() for p in self.providers)