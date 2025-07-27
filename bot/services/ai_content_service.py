# ===============================================================
# Файл: bot/services/ai_content_service.py (НОВЫЙ ФАЙЛ)
# Описание: Централизованный сервис для всех взаимодействий
# с генеративными AI моделями (Gemini). Обеспечивает
# отказоустойчивость, гибкую конфигурацию и чистоту кода.
# ===============================================================

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional

import aiohttp
from bot.config.settings import settings

logger = logging.getLogger(__name__)

# ПРИМЕЧАНИЕ: В реальном проекте этот класс настроек должен быть
# частью основного класса настроек в bot/config/settings.py
class AIContentSettings:
    gemini_api_key: str = settings.api_keys.gemini_api_key
    model_name: str = "gemini-1.5-pro-latest"
    flash_model_name: str = "gemini-1.5-flash-latest" # для простых задач
    max_retries: int = 3
    initial_retry_delay: float = 1.5
    request_timeout: int = 90

class AIContentService:
    """
    Центральный сервис для генерации контента с помощью AI.
    Инкапсулирует логику запросов, обработку ошибок и повторные попытки.
    """
    def __init__(self, http_session: aiohttp.ClientSession):
        self.session = http_session
        self.config = AIContentSettings()

        if not self.config.gemini_api_key:
            logger.critical("GEMINI_API_KEY is not configured. All AI features will be disabled.")
        
        self.headers = {'Content-Type': 'application/json'}
        self.params = {'key': self.config.gemini_api_key}

    async def _make_request(self, model_name: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Выполняет запрос к API Gemini с логикой повторных попыток."""
        if not self.config.gemini_api_key:
            return None
            
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        delay = self.config.initial_retry_delay

        for attempt in range(self.config.max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
                async with self.session.post(api_url, headers=self.headers, params=self.params, json=payload, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    
                    # Обработка ошибок, при которых стоит повторить запрос
                    if response.status in [429, 500, 503]:
                        logger.warning(f"AI API returned {response.status}. Retrying in {delay:.2f}s... (Attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        logger.error(f"AI API returned critical error {response.status}: {await response.text()}")
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Network error during AI request: {e}. Retrying in {delay:.2f}s... (Attempt {attempt + 1})")
                await asyncio.sleep(delay)
                delay *= 2
        
        logger.error(f"Failed to get response from AI API after {self.config.max_retries} retries.")
        return None

    async def generate_structured_content(self, prompt: str, json_schema: Dict) -> Optional[List[Dict[str, Any]]]:
        """
        Генерирует структурированный контент (JSON) на основе промпта и схемы.
        Использует самую мощную модель.
        """
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": json_schema,
                "temperature": 0.5
            }
        }
        result = await self._make_request(self.config.model_name, payload)
        
        if result and result.get('candidates'):
            try:
                text_content = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(text_content)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.error(f"Failed to parse structured JSON from AI response: {e}. Response: {result}")
                return None
        return None

    async def generate_summary(self, text_to_summarize: str) -> str:
        """
        Генерирует краткое саммари для текста. Использует быструю модель.
        """
        prompt = (
            "You are a crypto news analyst. Read the following news article and provide a very short, "
            "one-sentence summary in Russian (10-15 words max) that captures the main point. "
            f"Be concise and informative. Here is the article: \n\n{text_to_summarize}"
        )
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        
        result = await self._make_request(self.config.flash_model_name, payload)

        if result and result.get('candidates'):
            try:
                summary = result['candidates'][0]['content']['parts'][0]['text']
                return summary.strip()
            except (KeyError, IndexError):
                logger.warning("Could not extract summary text from AI response.")
        
        return "Не удалось проанализировать."
