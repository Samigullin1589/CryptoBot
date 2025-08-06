# ==================================================================================
# Файл: bot/services/crypto_center_service.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ИСПРАВЛЕННАЯ)
# Описание: Полностью самодостаточный и персонализированный сервис-оркестратор.
# ИСПРАВЛЕНИЕ: Параметр 'redis_client' в __init__ заменен на 'redis' для
# соответствия с DI-контейнером.
# ==================================================================================

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

import redis.asyncio as redis

from bot.config.settings import CryptoCenterServiceConfig
from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle, AirdropProject
from bot.texts.ai_prompts import get_personalized_alpha_prompt

logger = logging.getLogger(__name__)

class CryptoCenterService:
    """Персональный AI-ассистент для навигации в мире криптовалют."""

    # ИСПРАВЛЕНО: 'redis_client' -> 'redis'
    def __init__(self, redis: redis.Redis, ai_service: AIContentService,
                 news_service: NewsService, config: CryptoCenterServiceConfig):
        self.redis = redis
        self.ai_service = ai_service
        self.news_service = news_service
        self.config = config
        self.keys = KeyFactory

    async def _get_user_interest_profile(self, user_id: int) -> Dict[str, List[str]]:
        """Загружает или создаёт профиль интересов пользователя."""
        profile_key = self.keys.user_interest_profile(user_id)
        tags = await self.redis.smembers(f"{profile_key}:tags")
        coins = await self.redis.smembers(f"{profile_key}:coins")
        return {"tags": [t.decode('utf-8') for t in tags], "interacted_coins": [c.decode('utf-8') for c in coins]}

    async def update_user_interest(self, user_id: int, tags: List[str] = None, coins: List[str] = None):
        """Обновляет профиль интересов пользователя на основе его действий."""
        profile_key = self.keys.user_interest_profile(user_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            if tags:
                pipe.sadd(f"{profile_key}:tags", *tags)
            if coins:
                pipe.sadd(f"{profile_key}:coins", *coins)
            await pipe.execute()
        logger.debug(f"Updated interest profile for user {user_id} with tags={tags}, coins={coins}")

    async def _generate_alpha(self, user_id: int, alpha_type: str, json_schema: Dict) -> List[Dict[str, Any]]:
        """Универсальный метод для генерации персонализированной 'альфы'."""
        user_profile = await self._get_user_interest_profile(user_id)
        cache_key = self.keys.personalized_alpha_cache(user_id, alpha_type)

        if cached_data := await self.redis.get(cache_key):
            logger.info(f"Serving {alpha_type} alpha for user {user_id} from cache.")
            return json.loads(cached_data)

        logger.info(f"Generating fresh personalized {alpha_type} alpha for user {user_id}...")
        news_context = await self.news_service.get_raw_news_context(limit=self.config.news_context_limit)
        if not news_context:
            return []

        prompt = get_personalized_alpha_prompt(news_context, user_profile, alpha_type)
        result = await self.ai_service.generate_structured_content(prompt, json_schema)

        if result:
            logger.info(f"AI analysis for user {user_id} resulted in {len(result)} {alpha_type} opportunities.")
            await self.redis.set(cache_key, json.dumps(result, ensure_ascii=False), ex=self.config.alpha_cache_ttl_seconds)
            return result
        return []

    async def get_airdrop_alpha(self, user_id: int) -> List[AirdropProject]:
        """Получает персонализированный список Airdrop-проектов."""
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "status": {"type": "STRING"}, "tasks": {"type": "ARRAY", "items": {"type": "STRING"}}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "status", "tasks"]}}
        projects_data = await self._generate_alpha(user_id, "airdrop", json_schema)
        return [AirdropProject(**data) for data in projects_data]

    async def get_mining_alpha(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает персонализированные майнинг-сигналы."""
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "algorithm": {"type": "STRING"}, "hardware": {"type": "STRING"}, "status": {"type": "STRING"}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "algorithm", "hardware"]}}
        return await self._generate_alpha(user_id, "mining", json_schema)

    async def get_live_feed_with_summary(self) -> List[NewsArticle]:
        """Получает новостную ленту с AI-саммари."""
        cache_key = self.keys.live_feed_cache()
        if cached_data := await self.redis.get(cache_key):
            logger.info("Serving live feed from cache.")
            return [NewsArticle(**data) for data in json.loads(cached_data)]

        logger.info("Generating fresh live feed with summaries...")
        articles = await self.news_service.get_latest_news()
        if not articles:
            return []

        summary_tasks = [self.ai_service.generate_summary(article.body) for article in articles[:5]]
        summaries = await asyncio.gather(*summary_tasks)
        
        for article, summary in zip(articles, summaries):
            article.ai_summary = summary
            
        await self.redis.set(cache_key, json.dumps([a.model_dump() for a in articles]), ex=self.config.feed_cache_ttl_seconds)
        return articles

    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        """Получает список индексов выполненных задач для пользователя."""
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        completed_tasks = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int):
        """Переключает статус выполнения задачи и обновляет профиль интересов."""
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        task_index_str = str(task_index)
        
        if await self.redis.srem(progress_key, task_index_str):
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as NOT completed.")
        else:
            await self.redis.sadd(progress_key, task_index_str)
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as completed.")
            await self.update_user_interest(user_id, tags=['airdrop_hunter'])
