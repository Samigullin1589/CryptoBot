# bot/services/ai/openai_provider.py
import asyncio
import logging
from typing import Any, Dict, List, Optional

import backoff

try:
    from openai import APIConnectionError, OpenAI, RateLimitError
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    
    class APIConnectionError(Exception):
        pass
    
    class RateLimitError(Exception):
        pass
    
    OPENAI_AVAILABLE = False

from bot.services.ai.base import AIProvider
from bot.utils.text_utils import clip_text

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self.model = model
        self.timeout = timeout
        self.client: Optional[OpenAI] = None
        
        if not OPENAI_AVAILABLE:
            logger.warning("⚠️ OpenAI library not available")
            return
        
        try:
            self.client = OpenAI(api_key=api_key, timeout=timeout)
            logger.info(f"✅ OpenAI initialized (model: {model})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI: {e}")
            self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def get_name(self) -> str:
        return "OpenAI"

    @backoff.on_exception(
        backoff.expo,
        (APIConnectionError, RateLimitError),
        max_tries=3,
        on_backoff=lambda details: logger.warning(
            f"🔄 Retrying OpenAI request (attempt {details['tries']})"
        )
    )
    async def _request(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        
        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if response_format:
            request_params["response_format"] = response_format

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            **request_params
        )
        
        return (response.choices[0].message.content or "").strip()

    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": clip_text(prompt, 8000)})
        
        return await self._request(messages, temperature)

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
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": clip_text(prompt, 7000)}
        ]
        
        return await self._request(
            messages, 
            temperature,
            response_format={"type": "json_object"}
        )