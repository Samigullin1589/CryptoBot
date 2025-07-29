# ===============================================================
# Файл: bot/services/security_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Сервис, отвечающий за анализ сообщений на угрозы
# (спам, токсичность, скам) и самообучение системы.
# ===============================================================

import json
import logging
from typing import Dict, Any

import aiohttp
from async_lru import alru_cache

# Импортируем централизованные компоненты
# --- ИСПРАВЛЕНИЕ: Импортируем оба класса напрямую ---
from bot.config.settings import AppSettings, ApiKeysConfig
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.http_client import make_request
from bot.utils.models import AIVerdict

logger = logging.getLogger(__name__)

class SecurityService:
    """Сервис для анализа угроз и управления безопасностью."""

    # --- ИСПРАВЛЕНИЕ: Указываем правильный тип для конфига ---
    def __init__(self, http_session: aiohttp.ClientSession, config: ApiKeysConfig):
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
        """
        Инициализирует сервис.
        
        :param http_session: Общий экземпляр aiohttp.ClientSession.
        :param config: Конфигурация с API-ключами.
        """
        self.session = http_session
        self.config = config
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.config.gemini_api_key}"

    def _get_system_prompt(self) -> str:
        """Создает системный промпт для AI-анализатора безопасности."""
        return (
            "You are a security analysis bot for a Telegram chat about cryptocurrency. "
            "Analyze the following message. Respond with ONLY a valid JSON object. "
            "Do not add any other text or markdown formatting."
        )

    def _get_response_schema(self) -> Dict[str, Any]:
        """Определяет JSON-схему для структурированного ответа от AI."""
        return {
            "type": "OBJECT",
            "properties": {
                "intent": {
                    "type": "STRING",
                    "enum": ["advertisement", "scam", "phishing", "insult", "question", "other"],
                    "description": "Основное намерение сообщения."
                },
                "toxicity_score": {
                    "type": "NUMBER",
                    "description": "Оценка токсичности от 0.0 до 1.0."
                },
                "is_potential_scam": {
                    "type": "BOOLEAN",
                    "description": "True, если сообщение похоже на мошенничество (airdrop, private sale, 'pump-dump')."
                },
                "is_potential_phishing": {
                    "type": "BOOLEAN",
                    "description": "True, если сообщение содержит подозрительные ссылки, замаскированные под известные сервисы."
                }
            },
            "required": ["intent", "toxicity_score", "is_potential_scam", "is_potential_phishing"]
        }

    @alru_cache(maxsize=1024, ttl=300)
    async def analyze_message(self, text: str) -> AIVerdict:
        """
        Анализирует текст сообщения с помощью Gemini API для выявления угроз.
        Возвращает Pydantic-модель AIVerdict.
        """
        default_verdict = AIVerdict()
        if not self.config.gemini_api_key or not text.strip():
            return default_verdict

        prompt = f"{self._get_system_prompt()}\n\nMessage to analyze: '{text}'"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": self._get_response_schema()
            }
        }

        try:
            response_data = await make_request(self.session, self.api_url, "POST", json_data=payload, timeout=10)
            if not response_data or not response_data.get('candidates'):
                logger.warning(f"AI Security analysis returned no candidates for text: '{text[:50]}...'")
                return default_verdict

            verdict_text = response_data['candidates'][0]['content']['parts'][0]['text']
            verdict_dict = json.loads(verdict_text)
            logger.info(f"AI Security Verdict for '{text[:30]}...': {verdict_dict}")
            return AIVerdict(**verdict_dict)
        except Exception as e:
            logger.error(f"An error occurred during AI message analysis: {e}")
            return default_verdict
