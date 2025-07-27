# ===============================================================
# Файл: bot/services/crypto_center_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Сервис-оркестратор для Крипто-Центра. Использует
# NewsService и AIContentService для выполнения своих задач.
# Реализует надежное кэширование в Redis.
# ===============================================================

import json
import logging
from typing import List, Dict, Any, Optional

import redis.asyncio as redis

from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.utils.models import NewsArticle

logger = logging.getLogger(__name__)

class CryptoCenterService:
    """
    Сервис-оркестратор для управления данными Крипто-Центра.
    """
    def __init__(self, redis_client: redis.Redis, ai_service: AIContentService, news_service: NewsService):
        self.redis = redis_client
        self.ai_service = ai_service
        self.news_service = news_service
        
        # --- Redis Keys for Caching ---
        self.AIRDROP_CACHE_KEY = "cache:crypto_center:airdrops"
        self.MINING_CACHE_KEY = "cache:crypto_center:mining"
        self.FEED_CACHE_KEY = "cache:crypto_center:feed"
        
        # --- Cache TTLs in seconds ---
        self.ALPHA_CACHE_TTL = 3600 * 4  # 4 часа
        self.FEED_CACHE_TTL = 60 * 15     # 15 минут

    # --- Генерация "Альфы" ---

    async def generate_airdrop_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует или достает из кэша список Airdrop-проектов."""
        cached_data = await self.redis.get(self.AIRDROP_CACHE_KEY)
        if cached_data:
            logger.info("Serving airdrop alpha from cache.")
            return json.loads(cached_data)

        logger.info("Generating fresh airdrop alpha...")
        news_context = await self.news_service.get_aggregated_news_text()
        if not news_context:
            return []
        
        prompt = (
            "Действуй как крипто-исследователь. На основе предоставленных новостей, определи 3 самых перспективных проекта без токена, у которых вероятен airdrop. "
            "Для каждого проекта предоставь: 'id' (уникальный идентификатор в одно слово), 'name', 'description' (короткое описание), 'status', "
            "'tasks' (список из 3-5 действий) и 'guide_url'. "
            "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ. Если информации недостаточно, верни пустой массив. Контекст:\n\n"
            f"{news_context}"
        )
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "status": {"type": "STRING"}, "tasks": {"type": "ARRAY", "items": {"type": "STRING"}}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "status", "tasks"]}}
        
        result = await self.ai_service.generate_structured_content(prompt, json_schema)
        if result is not None: # Может вернуться пустой список, это валидный результат
            logger.info(f"AI analysis resulted in {len(result)} airdrop opportunities.")
            await self.redis.set(self.AIRDROP_CACHE_KEY, json.dumps(result, ensure_ascii=False), ex=self.ALPHA_CACHE_TTL)
            return result
        
        return []

    async def generate_mining_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует или достает из кэша список майнинг-сигналов."""
        cached_data = await self.redis.get(self.MINING_CACHE_KEY)
        if cached_data:
            logger.info("Serving mining alpha from cache.")
            return json.loads(cached_data)

        logger.info("Generating fresh mining alpha...")
        news_context = await self.news_service.get_aggregated_news_text()
        if not news_context:
            return []
        
        prompt = (
            "Действуй как майнинг-аналитик. На основе предоставленных новостей, определи 3 самых актуальных майнинг-возможности (ASIC/GPU/CPU). "
            "Для каждой предоставь: 'id', 'name', 'description', 'algorithm', 'hardware' (рекомендуемое оборудование), 'status' и 'guide_url'. "
            "ВСЕ ТЕКСТОВЫЕ ДАННЫЕ ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ. Если информации недостаточно, верни пустой массив. Контекст:\n\n"
            f"{news_context}"
        )
        json_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "algorithm": {"type": "STRING"}, "hardware": {"type": "STRING"}, "status": {"type": "STRING"}, "guide_url": {"type": "STRING"}}, "required": ["id", "name", "description", "algorithm", "hardware"]}}
        
        result = await self.ai_service.generate_structured_content(prompt, json_schema)
        if result is not None:
            logger.info(f"AI analysis resulted in {len(result)} mining opportunities.")
            await self.redis.set(self.MINING_CACHE_KEY, json.dumps(result, ensure_ascii=False), ex=self.ALPHA_CACHE_TTL)
            return result
            
        return []

    async def get_live_feed_with_summary(self) -> List[NewsArticle]:
        """Получает или достает из кэша новостную ленту с AI-саммари."""
        cached_data = await self.redis.get(self.FEED_CACHE_KEY)
        if cached_data:
            logger.info("Serving live feed from cache.")
            articles_dicts = json.loads(cached_data)
            return [NewsArticle(**data) for data in articles_dicts]

        logger.info("Generating fresh live feed with summaries...")
        articles = await self.news_service.get_latest_articles(limit=5)
        if not articles:
            return []

        # Параллельно запрашиваем саммари для каждой статьи
        summary_tasks = [self.ai_service.generate_summary(article.body) for article in articles]
        summaries = await asyncio.gather(*summary_tasks)
        
        for article, summary in zip(articles, summaries):
            article.ai_summary = summary
            
        articles_dicts = [article.model_dump() for article in articles]
        await self.redis.set(self.FEED_CACHE_KEY, json.dumps(articles_dicts), ex=self.FEED_CACHE_TTL)
        
        return articles

    # --- Управление прогрессом пользователя ---
    
    def _get_user_progress_key(self, user_id: int, airdrop_id: str) -> str:
        return f"user:{user_id}:airdrop_progress:{airdrop_id}"

    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        """Получает список индексов выполненных задач для пользователя."""
        progress_key = self._get_user_progress_key(user_id, airdrop_id)
        completed_tasks_str = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks_str])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int):
        """Переключает статус выполнения задачи."""
        progress_key = self._get_user_progress_key(user_id, airdrop_id)
        task_index_str = str(task_index)
        
        if await self.redis.sismember(progress_key, task_index_str):
            await self.redis.srem(progress_key, task_index_str)
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as NOT completed.")
        else:
            await self.redis.sadd(progress_key, task_index_str)
            logger.info(f"User {user_id} marked task {task_index} of airdrop '{airdrop_id}' as completed.")
