import json
import logging
from typing import Dict, Any, List, Set

import aiohttp
import redis.asyncio as redis
from aiogram.types import Message
from async_lru import alru_cache

logger = logging.getLogger(__name__)

class AIService:
    """
    Интеллектуальный сервис для анализа сообщений, управления базой знаний
    и реализации контура самообучения антиспам-системы.
    """
    def __init__(self, redis_client: redis.Redis, gemini_api_key: str):
        """
        Инициализирует сервис.
        
        :param redis_client: Асинхронный клиент для Redis.
        :param gemini_api_key: API-ключ для доступа к Google Gemini.
        """
        self.redis = redis_client
        self.api_key = gemini_api_key
        self.stop_words_key = "antispam:stop_words"
        self.spam_learning_dataset_key = "antispam:learning_dataset"

    @alru_cache(maxsize=1)
    async def get_stop_words(self) -> Set[str]:
        """
        Получает набор стоп-слов из Redis. Результат кешируется для производительности.
        """
        words = await self.redis.smembers(self.stop_words_key)
        return {word.decode('utf-8') for word in words}

    async def add_stop_word(self, word: str) -> bool:
        """
        Добавляет новое стоп-слово в базу данных.
        Возвращает True, если слово было добавлено, False - если уже существовало.
        """
        word = word.lower().strip()
        if not word:
            return False
        # Сбрасываем кеш, чтобы при следующем вызове get_stop_words получить актуальный список
        self.get_stop_words.cache_clear()
        return bool(await self.redis.sadd(self.stop_words_key, word))

    async def remove_stop_word(self, word: str) -> bool:
        """
        Удаляет стоп-слово из базы данных.
        Возвращает True, если слово было удалено, False - если его не было в списке.
        """
        word = word.lower().strip()
        self.get_stop_words.cache_clear()
        return bool(await self.redis.srem(self.stop_words_key, word))

    async def get_all_stop_words(self) -> List[str]:
        """Возвращает текущий список всех стоп-слов."""
        words_set = await self.get_stop_words()
        return sorted(list(words_set))

    @alru_cache(maxsize=1024, ttl=300)
    async def analyze_message(self, text: str) -> Dict[str, Any]:
        """
        Анализирует текст сообщения с помощью Gemini API для выявления угроз.
        Возвращает структурированный словарь с оценками.
        """
        default_verdict = {"intent": "other", "toxicity_score": 0.0, "is_potential_spam": False}
        
        if not self.api_key or not text.strip():
            return default_verdict

        prompt = (
            "You are a security analysis bot. Analyze the following message from a group chat. "
            "Respond with ONLY a valid JSON object. Do not add any other text or markdown formatting. "
            f"Message to analyze: '{text}'"
        )
        
        # Схема для получения структурированного ответа от Gemini
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "intent": {
                    "type": "STRING",
                    "enum": ["advertisement", "question", "insult", "link_sharing", "greeting", "other"]
                },
                "toxicity_score": {
                    "type": "NUMBER",
                    "description": "A score from 0.0 to 1.0 representing the message's toxicity."
                },
                "is_potential_spam": {
                    "type": "BOOLEAN",
                    "description": "True if the message looks like commercial spam, scam or unwanted advertisement."
                }
            },
            "required": ["intent", "toxicity_score", "is_potential_spam"]
        }

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": response_schema
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return default_verdict
                    
                    result = await response.json()
                    
                    if not result.get('candidates'):
                        logger.warning(f"Gemini API returned no candidates for text: '{text[:50]}...'")
                        return default_verdict

                    # Извлекаем и парсим JSON из ответа
                    verdict_text = result['candidates'][0]['content']['parts'][0]['text']
                    verdict = json.loads(verdict_text)
                    logger.info(f"AI Verdict for '{text[:30]}...': {verdict}")
                    return verdict

        except Exception as e:
            logger.error(f"An error occurred during AI message analysis: {e}")
            return default_verdict

    async def learn_from_spam(self, message: Message):
        """
        Сохраняет данные о спам-сообщении для последующего анализа и дообучения.
        Это ключевой метод для 'самообучения' системы.
        """
        if not message:
            return

        # Собираем важную информацию о спам-сообщении
        learning_data = {
            "timestamp": message.date.isoformat(),
            "user_id": message.from_user.id,
            "chat_id": message.chat.id,
            "text": message.text or message.caption,
            "entities": [entity.dict() for entity in message.entities or []],
            "banned_by": "admin_action" # Указываем, что это подтвержденный спам
        }
        
        # Сохраняем данные в Redis (в виде JSON-строки в списке)
        await self.redis.rpush(self.spam_learning_dataset_key, json.dumps(learning_data, ensure_ascii=False))
        logger.info(f"Learned from new spam message from user {message.from_user.id}")

