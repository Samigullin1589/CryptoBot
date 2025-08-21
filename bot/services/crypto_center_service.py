# bot/services/crypto_center_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис-оркестратор, предоставляющий персонализированный контент
# (Airdrops, Mining Alpha, новости) с помощью AI и кэширования.

import asyncio
import json
from typing import Any, Dict, List, Type, TypeVar

from bs4 import BeautifulSoup
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.texts.ai_prompts import get_personalized_alpha_prompt
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import AirdropProject, MiningProject, NewsArticle

# Generic TypeVar для Pydantic моделей
T = TypeVar("T", bound='BaseModel')


class CryptoCenterService:
    """
    Персональный AI-ассистент для навигации в мире криптовалют.
    Агрегирует, анализирует и кэширует данные, чтобы предоставить пользователю
    персонализированные рекомендации и новостные сводки.
    """

    def __init__(self, ai_service: AIContentService, news_service: NewsService):
        """Инициализирует сервис с необходимыми зависимостями."""
        self.redis: Redis = get_redis_client()
        self.ai_service = ai_service
        self.news_service = news_service
        self.config = settings.CRYPTO_CENTER
        self.keys = KeyFactory
        logger.info("Сервис CryptoCenterService инициализирован.")

    async def _get_user_interest_profile(self, user_id: int) -> Dict[str, List[str]]:
        """Загружает профиль интересов пользователя из Redis."""
        profile_key = self.keys.user_interest_profile(user_id)
        try:
            tags_raw, coins_raw = await asyncio.gather(
                self.redis.smembers(f"{profile_key}:tags"),
                self.redis.smembers(f"{profile_key}:coins")
            )
            return {"tags": list(tags_raw), "interacted_coins": list(coins_raw)}
        except Exception as e:
            logger.error(f"Не удалось загрузить профиль интересов для user_id={user_id}: {e}")
            return {"tags": [], "interacted_coins": []}

    async def update_user_interest(self, user_id: int, tags: List[str] = None, coins: List[str] = None):
        """Атомарно обновляет профиль интересов пользователя в Redis."""
        profile_key = self.keys.user_interest_profile(user_id)
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                if tags:
                    pipe.sadd(f"{profile_key}:tags", *tags)
                if coins:
                    pipe.sadd(f"{profile_key}:coins", *coins)
                await pipe.execute()
            logger.debug(f"Обновлен профиль интересов для user_id={user_id}.")
        except Exception as e:
            logger.error(f"Не удалось обновить профиль интересов для user_id={user_id}: {e}")

    async def _generate_alpha(self, user_id: int, alpha_type: str, model: Type[T]) -> List[T]:
        """
        Универсальный метод для генерации персонализированной 'альфы' (ценной информации).
        Сначала проверяет кэш, при его отсутствии обращается к AI, валидирует
        и кэширует результат.
        """
        cache_key = self.keys.personalized_alpha_cache(user_id, alpha_type)
        
        # 1. Попытка получить и валидировать данные из кэша
        try:
            if cached_data := await self.redis.get(cache_key):
                parsed_data = json.loads(cached_data)
                validated_items = [model.model_validate(item) for item in parsed_data]
                logger.info(f"Для user_id={user_id} {alpha_type} загружен из кэша.")
                return validated_items
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            logger.warning(f"Кэш {alpha_type} для user_id={user_id} поврежден ({e}), будет запрошен заново.")

        # 2. Генерация свежих данных через AI
        logger.info(f"Генерация свежего {alpha_type} для user_id={user_id} через AI...")
        user_profile = await self._get_user_interest_profile(user_id)
        prompt = get_personalized_alpha_prompt(user_profile, alpha_type)
        
        # Схема для AI должна описывать массив объектов
        json_schema = {"type": "array", "items": model.model_json_schema()}
        
        ai_result = await self.ai_service.get_structured_response(prompt, json_schema)

        # 3. Валидация и кэширование результата от AI
        if isinstance(ai_result, list):
            try:
                validated_items = [model.model_validate(item) for item in ai_result]
                logger.success(f"AI сгенерировал {len(validated_items)} валидных {alpha_type} для user_id={user_id}.")
                
                # Кэшируем только валидные данные
                await self.redis.set(
                    cache_key,
                    json.dumps([item.model_dump() for item in validated_items], ensure_ascii=False),
                    ex=self.config.ALPHA_CACHE_TTL_SECONDS
                )
                return validated_items
            except (ValidationError, TypeError) as e:
                logger.error(f"AI вернул данные для {alpha_type}, но они не прошли валидацию: {e}")
        
        logger.warning(f"AI не вернул валидных данных {alpha_type} для user_id={user_id}.")
        return []

    async def get_airdrop_alpha(self, user_id: int) -> List[AirdropProject]:
        """Получает персонализированный список перспективных Airdrop-проектов."""
        return await self._generate_alpha(user_id, "airdrop", AirdropProject)

    async def get_mining_alpha(self, user_id: int) -> List[MiningProject]:
        """Получает персонализированный список перспективных майнинг-проектов."""
        return await self._generate_alpha(user_id, "mining", MiningProject)

    async def get_live_feed_with_summary(self) -> List[NewsArticle]:
        """
        Формирует новостную ленту, обогащая свежие статьи краткими AI-саммари.
        Результат кэшируется.
        """
        cache_key = self.keys.live_feed_cache()
        try:
            if cached_data := await self.redis.get(cache_key):
                return [NewsArticle.model_validate(data) for data in json.loads(cached_data)]
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Кэш новостной ленты поврежден ({e}), будет сгенерирован заново.")

        logger.info("Генерация свежей новостной ленты с AI-саммари...")
        articles = await self.news_service.get_all_latest_news(limit=5)
        if not articles:
            return []

        async def summarize_article(article: NewsArticle):
            clean_text = BeautifulSoup(article.body, 'html.parser').get_text(separator=' ', strip=True)
            if clean_text:
                summary = await self.ai_service.get_text_response(clean_text, system_prompt="Суммируй новость в 3-4 коротких тезисах.")
                if summary and "К сожалению" not in summary:
                    article.ai_summary = summary
            return article

        # Параллельно запускаем задачи на суммаризацию
        summarized_articles = await asyncio.gather(*(summarize_article(art) for art in articles))
        
        try:
            articles_json = json.dumps([a.model_dump(mode='json') for a in summarized_articles], ensure_ascii=False)
            await self.redis.set(cache_key, articles_json, ex=self.config.FEED_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Не удалось сохранить кэш новостной ленты: {e}")
            
        return summarized_articles

    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        """Получает список индексов выполненных задач для конкретного Airdrop."""
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        completed_tasks = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int):
        """Переключает статус выполнения задачи для Airdrop."""
        progress_key = self.keys.user_airdrop_progress(user_id, airdrop_id)
        task_index_str = str(task_index)
        
        # SREM возвращает 1, если элемент был удален, и 0, если его не было.
        if await self.redis.srem(progress_key, task_index_str):
            logger.info(f"User {user_id} отметил задачу {task_index} airdrop'а '{airdrop_id}' как НЕВЫПОЛНЕННУЮ.")
        else:
            await self.redis.sadd(progress_key, task_index_str)
            logger.info(f"User {user_id} отметил задачу {task_index} airdrop'а '{airdrop_id}' как ВЫПОЛНЕННУЮ.")
            # Обновляем профиль интересов пользователя
            await self.update_user_interest(user_id, tags=['airdrop_hunter'])