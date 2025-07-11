import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
import aiohttp
import feedparser
from async_lru import alru_cache

from bot.config.settings import settings

logger = logging.getLogger(__name__)

class CryptoCenterService:
    """
    Сервис для управления данными Крипто-Центра, используя AI для генерации контента.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    # --- AI-POWERED, SELF-UPDATING METHODS ---

    async def _gather_live_data(self) -> str:
        """Собирает данные из новостных API и RSS-лент для анализа."""
        logger.info("Gathering live data for AI analysis...")
        all_text_content = ""
        
        # 1. Сбор данных из CryptoCompare API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(settings.crypto_center_news_api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get("Data", [])
                        for article in articles[:10]: # Берем 10 свежих
                            all_text_content += f"Title: {article.get('title', '')}\nBody: {article.get('body', '')}\n\n"
        except Exception as e:
            logger.error(f"Failed to fetch from CryptoCompare: {e}")

        # 2. Сбор данных из RSS-лент
        for feed_url in settings.alpha_rss_feeds:
            try:
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                for entry in feed.entries[:3]: # Берем 3 свежих из каждой ленты
                    all_text_content += f"Title: {entry.title}\nSummary: {entry.summary}\n\n"
            except Exception as e:
                logger.error(f"Failed to parse RSS feed {feed_url}: {e}")
        
        logger.info(f"Gathered {len(all_text_content)} characters of live data for analysis.")
        return all_text_content


    async def _generate_alpha_from_ai(self, prompt: str, json_schema: Dict) -> List[Dict[str, Any]]:
        """Универсальная функция для запроса к Gemini API."""
        if not settings.gemini_api_key:
            logger.error("GEMINI_API_KEY is not set. Cannot generate AI alpha.")
            return []

        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": json_schema}
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=45) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return []
                    result = await response.json()
                    text_content = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '[]')
                    parsed_json = json.loads(text_content)
                    return parsed_json
        except Exception as e:
            logger.error(f"An error occurred during AI Alpha generation: {e}")
            return []

    @alru_cache(maxsize=2, ttl=3600 * 4)  # Кэшируем на 4 часа
    async def generate_airdrop_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует актуальный список Airdrop-проектов на основе живых данных."""
        live_data = await self._gather_live_data()
        if not live_data:
            logger.warning("No live data gathered for airdrop analysis.")
            return []
        
        prompt = (
            "You are a crypto researcher. Based ONLY on the provided recent news and articles below, identify the top 3 most promising airdrop opportunities. "
            "For each, extract the project name, a short summary of why it's a hot opportunity right now, a list of 3-5 concrete actions to take, and an official link if available. "
            "If the context doesn't contain enough information, return an empty array. Context:\n\n"
            f"{live_data}"
        )
        json_schema = { "type": "ARRAY", "items": { "type": "OBJECT", "properties": { "id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "status": {"type": "STRING"}, "tasks": {"type": "ARRAY", "items": {"type": "STRING"}}, "guide_url": {"type": "STRING"} }, "required": ["id", "name", "description", "status", "tasks"] } }
        
        result = await self._generate_alpha_from_ai(prompt, json_schema)
        logger.info(f"AI analysis resulted in {len(result)} airdrop opportunities.")
        return result

    @alru_cache(maxsize=2, ttl=3600 * 4)
    async def generate_mining_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует актуальные майнинг-сигналы на основе живых данных."""
        live_data = await self._gather_live_data()
        if not live_data:
            logger.warning("No live data gathered for mining analysis.")
            return []
            
        prompt = (
            "You are a mining analyst. Based ONLY on the provided recent news and articles below, identify the top 3 most relevant mining opportunities (for ASIC, GPU, or CPU). "
            "Focus on emerging trends. For each, extract the opportunity name, a short summary of why it's relevant, the algorithm, recommended hardware, and an official link if available. "
            "If the context doesn't contain enough information, return an empty array. Context:\n\n"
            f"{live_data}"
        )
        json_schema = { "type": "ARRAY", "items": { "type": "OBJECT", "properties": { "id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "algorithm": {"type": "STRING"}, "hardware": {"type": "STRING"}, "status": {"type": "STRING"}, "guide_url": {"type": "STRING"} }, "required": ["id", "name", "description", "algorithm", "hardware"] } }
        
        result = await self._generate_alpha_from_ai(prompt, json_schema)
        logger.info(f"AI analysis resulted in {len(result)} mining opportunities.")
        return result

    # --- Методы для работы с прогрессом пользователя ---
    
    def _get_user_progress_key(self, user_id: int, airdrop_id: str) -> str:
        return f"user:{user_id}:airdrop:{airdrop_id}:completed_tasks"

    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        progress_key = self._get_user_progress_key(user_id, airdrop_id)
        completed_tasks_str = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks_str])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int) -> bool:
        progress_key = self._get_user_progress_key(user_id, airdrop_id)
        task_index_str = str(task_index)
        if await self.redis.sismember(progress_key, task_index_str):
            await self.redis.srem(progress_key, task_index_str)
            return False
        else:
            await self.redis.sadd(progress_key, task_index_str)
            return True
