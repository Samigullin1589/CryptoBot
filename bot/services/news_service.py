# bot/services/news_service.py
# Дата обновления: 23.08.2025
# Версия: 2.1.0
# Описание: Отказоустойчивый сервис-агрегатор новостей.

import asyncio
import hashlib
import json
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.http_client import HttpClient
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle, parse_datetime

class NewsService:
    """
    Агрегирует, дедуплицирует, валидирует и кэширует новости в Redis.
    """

    def __init__(self, redis_client: Redis, http_client: HttpClient):
        """Инициализирует сервис с зависимостями."""
        self.redis = redis_client
        self.http_client = http_client
        self.config = settings.news_service
        self.keys = KeyFactory
        logger.info("Сервис NewsService инициализирован.")

    async def get_all_latest_news(self, limit: int = 30) -> List[NewsArticle]:
        """
        Основной метод для получения новостей.
        """
        cached_news = await self._get_cached_news()
        if cached_news:
            return cached_news[:limit]

        logger.info("Кэш новостей пуст. Запускаю обновление...")
        return await self.update_news_cache(limit=limit)

    async def update_news_cache(self, limit: int = 30) -> List[NewsArticle]:
        """
        Принудительно обновляет кэш новостей.
        """
        tasks = [self._fetch_rss(feed) for feed in self.config.feeds.main_rss_feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_articles = [item for res in results if isinstance(res, list) for item in res]
        
        unique_articles = self._deduplicate_articles(raw_articles)
        unique_articles.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        try:
            validated_articles = [NewsArticle.model_validate(art) for art in unique_articles]
            await self._cache_articles(validated_articles)
            return validated_articles[:limit]
        except ValidationError as e:
            logger.error(f"Ошибка валидации новостей перед кэшированием: {e}")
            return []
            
    async def _fetch_rss(self, url: str) -> List[Dict[str, Any]]:
        """Получает и парсит новости из RSS-фида."""
        try:
            response_text = await self.http_client.get(url, response_type='text')
            soup = BeautifulSoup(response_text, 'xml')
            
            articles = []
            for item in soup.find_all('item')[:self.config.news_limit_per_source]:
                title = item.find('title').text if item.find('title') else 'Без заголовка'
                link = item.find('link').text if item.find('link') else ''
                pub_date_str = item.find('pubDate').text if item.find('pubDate') else ''
                
                articles.append({
                    "title": title,
                    "url": link,
                    "source": url.split('/')[2],
                    "timestamp": parse_datetime(pub_date_str),
                })
            return articles
        except Exception as e:
            logger.error(f"Не удалось получить новости из RSS {url}: {e}")
            return []

    def _deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Удаляет дубликаты новостей по URL."""
        seen = set()
        return [a for a in articles if a.get("url") and a["url"] not in seen and not seen.add(a["url"])]

    async def _cache_articles(self, articles: List[NewsArticle]):
        """Сохраняет список новостей в кэш Redis."""
        try:
            data = json.dumps([a.model_dump(mode='json') for a in articles])
            await self.redis.set(self.keys.news_deduplication_set(), data, ex=self.config.cache_ttl_seconds)
        except Exception as e:
            logger.error(f"Ошибка при сохранении новостей в кэш Redis: {e}")

    async def _get_cached_news(self) -> Optional[List[NewsArticle]]:
        """Получает и валидирует список новостей из кэша Redis."""
        try:
            data = await self.redis.get(self.keys.news_deduplication_set())
            if not data: return None
            return [NewsArticle.model_validate(item) for item in json.loads(data)]
        except (json.JSONDecodeError, ValidationError):
            return None
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша новостей из Redis: {e}")
            return None