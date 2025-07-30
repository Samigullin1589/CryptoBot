# ===============================================================
# Файл: bot/services/crypto_center_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Сервис-оркестратор для Крипто-Центра, полностью
# интегрированный в архитектуру бота.
# ===============================================================

import json
import logging
from typing import List, Dict, Any, Optional

import redis.asyncio as redis

from bot.config.settings import CryptoCenterServiceConfig
from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle
from bot.texts.ai_prompts import get_airdrop_alpha_prompt, get_mining_alpha_prompt

logger = logging.getLogger(__name__)

class CryptoCenterService:
    """Сервис-оркестратор для управления данными Крипто-Центра."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        ai_service: AIContentService,
        news_service: NewsService,
        config: CryptoCenterServiceConfig
    ):
        self.redis = redis_client
        self.ai_service = ai_service
        self.news_service = news_service
        self.config = config
        self.keys = KeyFactory

    async def _get_news_context(self) -> Optional[str]:
        """Собирает текстовый контекст из последних новостей."""
        articles = await self.news_service.get_latest_news()
        if not articles:
            logger.warning("Нет новостей для анализа в Crypto Center.")
            return None
        # Объединяем тексты последних новостей в один большой контекст
        return "\n\n---\n\n".join([f"Title: {a.title}\nBody: {a.body}" for a in articles[:self.config.news_context_limit]])

    # --- Генерация "Альфы" ---
    
    async def generate_airdrop_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует или достает из кэша список Airdrop-проектов."""
        cache_key = self.keys.airdrop_alpha_cache()
        if cached_data := await self.redis.get(cache_key):
            logger.info("Serving airdrop alpha from cache.")
            return json.loads(cached_data)

        logger.info("Generating fresh airdrop alpha...")
        if not (news_context := await self._get_news_context()):
            return []
        
        prompt = get_airdrop_alpha_prompt(news_context)
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "status": {"type": "STRING"}, "tasks": {"type": "ARRAY", "items": {"type": "STRING"}}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "status", "tasks"]}}
        
        result = await self.ai_service.generate_structured_content(prompt, json_schema)
        if result is not None:
            logger.info(f"AI analysis resulted in {len(result)} airdrop opportunities.")
            await self.redis.set(cache_key, json.dumps(result, ensure_ascii=False), ex=self.config.alpha_cache_ttl_seconds)
            return result
        
        return []

    async def generate_mining_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует или достает из кэша список майнинг-сигналов."""
        cache_key = self.keys.mining_alpha_cache()
        if cached_data := await self.redis.get(cache_key):
            logger.info("Serving mining alpha from cache.")
            return json.loads(cached_data)

        logger.info("Generating fresh mining alpha...")
        if not (news_context := await self._get_news_context()):
            return []
        
        prompt = get_mining_alpha_prompt(news_context)
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "algorithm": {"type": "STRING"}, "hardware": {"type": "STRING"}, "status": {"type": "STRING"}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "algorithm", "hardware"]}}
        
        result = await self.ai_service.generate_structured_content(prompt, json_schema)
        if result is not None:
            logger.info(f"AI analysis resulted in {len(result)} mining opportunities.")
            await self.redis.set(cache_key, json.dumps(result, ensure_ascii=False), ex=self.config.alpha_cache_ttl_seconds)
            return result
            
        return []

    async def get_live_feed_with_summary(self) -> List[NewsArticle]:
        """Получает или достает из кэша новостную ленту с AI-саммари."""
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

    # --- Управление прогрессом пользователя ---
    
    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        """Получает список индексов выполненных задач для пользователя."""
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        completed_tasks = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int):
        """Переключает статус выполнения задачи."""
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        task_index_str = str(task_index)
        
        # SREM возвращает 1, если элемент был удален, и 0, если его не было
        if await self.redis.srem(progress_key, task_index_str):
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as NOT completed.")
        else:
            await self.redis.sadd(progress_key, task_index_str)
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as completed.")
