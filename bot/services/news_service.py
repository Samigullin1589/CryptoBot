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
        self.config = settings.NEWS
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
        tasks = [self._fetch_cryptopanic(), self._fetch_newsapi()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_articles = [item for res in results if isinstance(res, list) for item in res]
        
        unique_articles = self._deduplicate_articles(raw_articles)
        unique_articles.sort(key=lambda x: x.get("published_at"), reverse=True)

        enrich_tasks = [self._fetch_article_body(article) for article in unique_articles[:self.config.ENRICH_LIMIT]]
        enriched_articles = await asyncio.gather(*enrich_tasks)

        try:
            validated_articles = [NewsArticle.model_validate(art) for art in enriched_articles]
            await self._cache_articles(validated_articles)
            return validated_articles[:limit]
        except ValidationError as e:
            logger.error(f"Ошибка валидации новостей перед кэшированием: {e}")
            return []

    async def _fetch_cryptopanic(self) -> List[Dict[str, Any]]:
        """Получает новости из API CryptoPanic."""
        if not settings.CRYPTOPANIC_API_KEY: return []
        params = {"auth_token": settings.CRYPTOPANIC_API_KEY.get_secret_value(), "kind": "news", "public": "true"}
        try:
            data = await self.http_client.get(self.config.CRYPTOPANIC_URL, params=params)
            return [{"id": item.get("id"), "title": item.get("title"), "url": item.get("url"), "source": item.get("source", {}).get("title"), "published_at": parse_datetime(item.get("published_at"))} for item in data.get("results", [])]
        except Exception as e:
            logger.error(f"Не удалось получить новости от CryptoPanic: {e}")
            return []

    async def _fetch_newsapi(self) -> List[Dict[str, Any]]:
        """Получает новости из NewsAPI."""
        if not settings.NEWS_API_KEY: return []
        params = {"q": "crypto OR bitcoin OR ethereum OR blockchain", "sortBy": "publishedAt", "language": self.config.LANGUAGE, "pageSize": self.config.PAGE_SIZE, "apiKey": settings.NEWS_API_KEY.get_secret_value()}
        try:
            data = await self.http_client.get(self.config.NEWSAPI_URL, params=params)
            return [{"id": hashlib.sha1(item.get("url", "").encode()).hexdigest(), "title": item.get("title"), "url": item.get("url"), "source": item.get("source", {}).get("name"), "published_at": parse_datetime(item.get("publishedAt"))} for item in data.get("articles", [])]
        except Exception as e:
            logger.error(f"Не удалось получить новости от NewsAPI: {e}")
            return []

    async def _fetch_article_body(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Пытается загрузить и очистить полный текст статьи."""
        url = article_data.get("url")
        if not url:
            article_data["body"] = ""
            return article_data
        
        try:
            html = await self.http_client.get(url, response_type='text')
            soup = BeautifulSoup(html, "html.parser")
            for script_or_style in soup(["script", "style"]): script_or_style.decompose()
            text = soup.get_text(separator="\n", strip=True)
            article_data["body"] = "\n".join(line for line in text.splitlines() if line.strip())
        except Exception as e:
            logger.warning(f"Не удалось загрузить тело статьи {url}: {e}")
            article_data["body"] = ""
        
        return article_data

    def _deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Удаляет дубликаты новостей по URL."""
        seen = set()
        return [a for a in articles if a.get("url") and a["url"] not in seen and not seen.add(a["url"])]

    async def _cache_articles(self, articles: List[NewsArticle]):
        """Сохраняет список новостей в кэш Redis."""
        try:
            data = json.dumps([a.model_dump(mode='json') for a in articles])
            await self.redis.set(self.keys.news_cache(), data, ex=self.config.CACHE_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Ошибка при сохранении новостей в кэш Redis: {e}")

    async def _get_cached_news(self) -> Optional[List[NewsArticle]]:
        """Получает и валидирует список новостей из кэша Redis."""
        try:
            data = await self.redis.get(self.keys.news_cache())
            if not data: return None
            return [NewsArticle.model_validate(item) for item in json.loads(data)]
        except (json.JSONDecodeError, ValidationError):
            return None
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша новостей из Redis: {e}")
            return None