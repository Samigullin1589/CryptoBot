# ==================================================================================
# Файл: bot/services/crypto_center_service.py (ВЕРСИЯ "ГЕНИЙ 3.0" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Полностью самодостаточный и персонализированный сервис-оркестратор.
# ИСПРАВЛЕНИЕ: Добавлена надёжная проверка и десериализация данных,
#              получаемых как из кэша, так и напрямую от AI.
# ==================================================================================

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

import redis.asyncio as redis
from bs4 import BeautifulSoup

from bot.config.settings import CryptoCenterServiceConfig
from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle, AirdropProject
from bot.texts.ai_prompts import get_personalized_alpha_prompt

logger = logging.getLogger(__name__)

class CryptoCenterService:
    """Персональный AI-ассистент для навигации в мире криптовалют."""

    def __init__(self, redis: redis.Redis, ai_service: AIContentService,
                 news_service: NewsService, config: CryptoCenterServiceConfig):
        self.redis = redis
        self.ai_service = ai_service
        self.news_service = news_service
        self.config = config
        self.keys = KeyFactory

    async def _get_user_interest_profile(self, user_id: int) -> Dict[str, List[str]]:
        profile_key = self.keys.user_interest_profile(user_id)
        tags_raw = await self.redis.smembers(f"{profile_key}:tags")
        coins_raw = await self.redis.smembers(f"{profile_key}:coins")
        return {"tags": [t for t in tags_raw], "interacted_coins": [c for c in coins_raw]}

    async def update_user_interest(self, user_id: int, tags: List[str] = None, coins: List[str] = None):
        profile_key = self.keys.user_interest_profile(user_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            if tags: pipe.sadd(f"{profile_key}:tags", *tags)
            if coins: pipe.sadd(f"{profile_key}:coins", *coins)
            await pipe.execute()

    async def _generate_alpha(self, user_id: int, alpha_type: str, json_schema: Dict) -> List[Dict[str, Any]]:
        """Универсальный метод для генерации персонализированной 'альфы' с помощью AI-поиска."""
        user_profile = await self._get_user_interest_profile(user_id)
        cache_key = self.keys.personalized_alpha_cache(user_id, alpha_type)

        if cached_data := await self.redis.get(cache_key):
            logger.info(f"Serving {alpha_type} alpha for user {user_id} from cache.")
            try:
                # Десериализуем JSON-строку из кэша
                return json.loads(cached_data)
            except json.JSONDecodeError:
                logger.error("Failed to decode cached data, fetching fresh.")
        
        logger.info(f"Generating fresh personalized {alpha_type} alpha for user {user_id} via AI Search...")
        
        prompt = get_personalized_alpha_prompt(user_profile, alpha_type)
        result = await self.ai_service.generate_structured_content(prompt, json_schema)

        if result:
            # ИСПРАВЛЕНО: Добавлена проверка на случай, если AI вернул строку вместо объекта
            if isinstance(result, str):
                try: 
                    result = json.loads(result)
                except json.JSONDecodeError:
                    logger.error(f"AI returned a non-JSON string for {alpha_type}: {result}")
                    return []
            
            logger.info(f"AI Search for user {user_id} found {len(result)} {alpha_type} opportunities.")
            await self.redis.set(cache_key, json.dumps(result, ensure_ascii=False), ex=self.config.alpha_cache_ttl_seconds)
            return result
        
        logger.warning(f"AI Search for user {user_id} returned no valid {alpha_type} opportunities.")
        return []

    async def get_airdrop_alpha(self, user_id: int) -> List[AirdropProject]:
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "status": {"type": "STRING"}, "tasks": {"type": "ARRAY", "items": {"type": "STRING"}}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "status", "tasks"]}}
        projects_data = await self._generate_alpha(user_id, "airdrop", json_schema)
        
        if not isinstance(projects_data, list):
             logger.error(f"Airdrop alpha data is not a list after generation: {type(projects_data)}")
             return []
        
        return [AirdropProject(**data) for data in projects_data]

    async def get_mining_alpha(self, user_id: int) -> List[Dict[str, Any]]:
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "algorithm": {"type": "STRING"}, "hardware": {"type": "STRING"}, "status": {"type": "STRING"}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "algorithm", "hardware"]}}
        return await self._generate_alpha(user_id, "mining", json_schema)

    async def get_live_feed_with_summary(self) -> List[NewsArticle]:
        cache_key = self.keys.live_feed_cache()
        if cached_data := await self.redis.get(cache_key):
            return [NewsArticle(**data) for data in json.loads(cached_data)]

        logger.info("Generating fresh live feed with summaries...")
        articles = await self.news_service.get_all_latest_news()
        if not articles:
            return []

        summary_tasks = []
        for article in articles[:5]:
            clean_text = BeautifulSoup(article.body, 'html.parser').get_text(separator=' ', strip=True)
            if clean_text:
                summary_tasks.append(self.ai_service.generate_summary(clean_text))
        
        summaries = await asyncio.gather(*summary_tasks, return_exceptions=True)
        
        for article, summary in zip(articles, summaries):
            if isinstance(summary, str):
                article.ai_summary = summary
            else:
                logger.error(f"Ошибка при суммаризации статьи '{article.title}': {summary}")
            
        await self.redis.set(cache_key, json.dumps([a.model_dump(mode='json') for a in articles]), ex=self.config.feed_cache_ttl_seconds)
        return articles

    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        completed_tasks = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int):
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        task_index_str = str(task_index)
        
        if await self.redis.srem(progress_key, task_index_str):
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as NOT completed.")
        else:
            await self.redis.sadd(progress_key, task_index_str)
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as completed.")
            await self.update_user_interest(user_id, tags=['airdrop_hunter'])