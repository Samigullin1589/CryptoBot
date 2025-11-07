# bot/services/ai/gemini_provider.py
import logging
from typing import Any, Dict, Optional

import backoff

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    from google.generativeai.types import (
        GenerationConfig,
        HarmBlockThreshold,
        HarmCategory,
    )
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GenerationConfig = object
    HarmCategory = object
    HarmBlockThreshold = object
    GEMINI_AVAILABLE = False
    
    class _GoogleExceptionStub(Exception):
        pass
    
    class _GoogleExceptions:
        ResourceExhausted = _GoogleExceptionStub
        ServiceUnavailable = _GoogleExceptionStub
        GoogleAPIError = _GoogleExceptionStub
    
    google_exceptions = _GoogleExceptions()

from bot.services.ai.base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    def __init__(
        self, 
        api_key: str, 
        pro_model: str, 
        flash_model: str
    ):
        self.pro_model = None
        self.flash_model = None
        
        if not GEMINI_AVAILABLE:
            logger.warning("⚠️ Gemini library not available")
            return
        
        try:
            genai.configure(api_key=api_key)
            
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            self.pro_model = genai.GenerativeModel(
                pro_model,
                safety_settings=safety_settings
            )
            
            self.flash_model = genai.GenerativeModel(
                flash_model,
                safety_settings=safety_settings
            )
            
            logger.info(f"✅ Gemini initialized (Pro: {pro_model}, Flash: {flash_model})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini: {e}")
            self.pro_model = None
            self.flash_model = None

    def is_available(self) -> bool:
        return self.pro_model is not None

    def get_name(self) -> str:
        return "Gemini"

    @backoff.on_exception(
        backoff.expo,
        (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable),
        max_tries=3,
        on_backoff=lambda details: logger.warning(
            f"🔄 Retrying Gemini request (attempt {details['tries']})"
        )
    )
    async def _request(
        self, 
        model, 
        contents: Any, 
        temperature: float,
        is_json: bool = False
    ) -> str:
        if not model:
            raise RuntimeError("Gemini model not initialized")
        
        gen_config = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json" if is_json else "text/plain",
        )
        
        response = await model.generate_content_async(
            contents=contents,
            generation_config=gen_config
        )
        
        return response.text.strip()

    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        return await self._request(self.pro_model, full_prompt, temperature)

    async def generate_json(
        self, 
        prompt: str, 
        json_schema: Dict[str, Any],
        temperature: float = 0.1
    ) -> str:
        import json
        
        system_prompt = (
            "You must respond ONLY with valid JSON that matches the provided schema. "
            "Do not include any explanations, comments, or markdown formatting. "
            f"JSON schema: {json.dumps(json_schema, ensure_ascii=False, indent=2)}"
        )
        
        full_prompt = f"{system_prompt}\n\n{prompt}"
        
        return await self._request(self.flash_model, full_prompt, temperature, is_json=True)

    async def analyze_image(
        self, 
        prompt: str, 
        image_bytes: bytes,
        temperature: float = 0.1
    ) -> str:
        if not self.flash_model:
            raise RuntimeError("Gemini Flash model not initialized")
        
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        
        return await self._request(
            self.flash_model,
            [prompt, image_part],
            temperature,
            is_json=True
        )