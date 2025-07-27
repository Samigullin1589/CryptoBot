# ===============================================================
# Файл: bot/services/security_service.py (НОВЫЙ ФАЙЛ)
# Описание: Основной сервис безопасности, отвечающий за анализ
# сообщений на угрозы и самообучение. Заменяет часть AIService.
# ===============================================================

import asyncio
import json
import logging
from typing import Dict, Any

import aiohttp
import redis.asyncio as redis
from aiogram.types import Message
from bot.config.settings import settings

logger = logging.getLogger(__name__)

# ПРИМЕЧАНИЕ: В реальном проекте этот класс настроек должен быть
# частью основного класса настроек в bot/config/settings.py
class SecurityServiceSettings:
    gemini_api_key: str = settings.api_keys.gemini_api_key
    model_name: str = "gemini-1.5-flash-latest"
    max_retries: int = 3
    initial_retry_delay: float = 1.0
    request_timeout: int = 15

class SecurityService:
    """
    Сервис для анализа сообщений на угрозы и обучения на подтвержденных случаях спама.
    """
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        """
        Инициализирует сервис.
        
        :param redis_client: Асинхронный клиент Redis.
        :param http_session: Общий экземпляр aiohttp.ClientSession.
        """
        self.redis = redis_client
        self.session = http_session
        self.config = SecurityServiceSettings()
        self.spam_learning_dataset_key = "antispam:learning_dataset"

        if not self.config.gemini_api_key:
            logger.warning("Gemini API key is not configured. Threat analysis will be disabled.")
        
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model_name}:generateContent"
        self.headers = {'Content-Type': 'application/json'}
        self.params = {'key': self.config.gemini_api_key}

    def _create_prompt_and_schema(self, text: str) -> tuple[str, dict]:
        """Создает промпт и схему для анализа угрозы в сообщении."""
        prompt = (
            "You are a security analysis bot for a Telegram chat about cryptocurrency and mining. "
            "Your task is to analyze the following message and classify it according to the provided JSON schema. "
            "Focus on identifying specific crypto-related threats like phishing links disguised as airdrops, fake giveaways, "
            "impersonation of famous people to promote scams, or direct offers of 'guaranteed profit'. "
            "Respond with ONLY a valid JSON object. Do not add any other text or markdown formatting.\n\n"
            f"Message to analyze: '{text}'"
        )
        
        schema = {
            "type": "OBJECT",
            "properties": {
                "is_threat": {
                    "type": "BOOLEAN",
                    "description": "True if the message contains any kind of threat (spam, scam, insult, etc.)."
                },
                "threat_type": {
                    "type": "STRING",
                    "enum": ["none", "spam", "scam", "phishing", "insult", "other"],
                    "description": "The specific category of the threat."
                },
                "confidence_score": {
                    "type": "NUMBER",
                    "description": "A score from 0.0 to 1.0 representing your confidence in the threat assessment."
                },
                "analysis": {
                    "type": "STRING",
                    "description": "A brief, one-sentence explanation in Russian for your assessment."
                }
            },
            "required": ["is_threat", "threat_type", "confidence_score", "analysis"]
        }
        return prompt, schema

    async def _execute_analysis_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Выполняет запрос к API с логикой повторных попыток."""
        retries = self.config.max_retries
        delay = self.config.initial_retry_delay
        default_verdict = {"is_threat": False, "threat_type": "none", "confidence_score": 0.0, "analysis": "Analysis disabled or failed."}

        for attempt in range(retries):
            try:
                timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
                async with self.session.post(self.api_url, headers=self.headers, params=self.params, json=payload, timeout=timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        if not result.get('candidates'):
                            logger.warning(f"Gemini API returned no candidates for security analysis. Response: {result}")
                            return default_verdict
                        
                        verdict_text = result['candidates'][0]['content']['parts'][0]['text']
                        return json.loads(verdict_text)

                    elif response.status in [500, 502, 503, 504]:
                        logger.warning(f"Security analysis API returned {response.status}. Retrying... (Attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        logger.error(f"Security analysis API returned HTTP {response.status}: {await response.text()}")
                        return default_verdict
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Network error during security analysis: {e}. Retrying... (Attempt {attempt + 1})")
                await asyncio.sleep(delay)
                delay *= 2
        
        logger.error(f"Failed to analyze message after {retries} retries.")
        return default_verdict

    async def analyze_message(self, text: str) -> Dict[str, Any]:
        """
        Анализирует текст сообщения с помощью Gemini API для выявления угроз.
        Возвращает структурированный словарь с оценками.
        """
        default_verdict = {"is_threat": False, "threat_type": "none", "confidence_score": 0.0, "analysis": "Analysis disabled or failed."}
        
        if not self.config.gemini_api_key or not text or not text.strip():
            return default_verdict

        prompt, schema = self._create_prompt_and_schema(text)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0.2
            }
        }
        
        try:
            verdict = await self._execute_analysis_request(payload)
            logger.info(f"AI Security Verdict for '{text[:50].strip()}...': {verdict}")
            return verdict
        except Exception as e:
            logger.error(f"Unexpected error in analyze_message: {e}", exc_info=True)
            return default_verdict

    async def learn_from_spam(self, message: Message, threat_verdict: Dict[str, Any]):
        """
        Сохраняет данные о спам-сообщении для последующего анализа и дообучения.
        """
        if not message:
            return

        learning_data = {
            "timestamp_utc": message.date.isoformat(),
            "user_id": message.from_user.id,
            "chat_id": message.chat.id,
            "text": message.text or message.caption,
            "entities": [entity.model_dump() for entity in message.entities or []],
            "confirmation_source": "admin_action", # Указываем, что это подтвержденный спам
            "initial_verdict": threat_verdict # Сохраняем первоначальный вердикт AI
        }
        
        await self.redis.rpush(self.spam_learning_dataset_key, json.dumps(learning_data, ensure_ascii=False))
        logger.info(f"Learned from new spam message from user {message.from_user.id}")

