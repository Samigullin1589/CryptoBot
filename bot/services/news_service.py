# bot/services/news_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Отказоустойчивый сервис-агрегатор новостей из нескольких источников
# с интеллектуальным обогащением данных и кэшированием в Redis.

import asyncio
import hashlib
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.dependencies import get_redis_client
from bot.utils.http_client import http_session
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle, parse_datetime


class NewsService:
    """
    Агрегирует новости из CryptoPanic и NewsAPI, обогащает их полным текстом,
    дедуплицирует, валидирует и кэширует в Redis.
    """

    def __init__(self):
        """Инициализирует сервис с зависимостями и конфигурацией."""
        self.redis: Redis = get_redis_client()
        self.config = settings.NEWS
        self.keys = KeyFactory
        logger.info("Сервис NewsService инициализирован.")

    async def get_all_latest_news(self, limit: int = 30) -> List[NewsArticle]:
        """
        Основной метод для получения новостей. Сначала проверяет кэш,
        если он пуст или устарел — запускает полное обновление.
        """
        cached_news = await self._get_cached_news()
        if cached_news:
            return cached_news[:limit]

        logger.info("Кэш новостей пуст или устарел. Запускаю полное обновление...")
        return await self.update_news_cache(limit=limit)

    async def update_news_cache(self, limit: int = 30) -> List[NewsArticle]:
        """
        Принудительно обновляет кэш новостей: получает данные из всех источников,
        обогащает их, дедуплицирует и сохраняет в Redis.
        """
        # 1. Параллельно получаем "сырые" данные из всех источников
        fetch_tasks = [
            self._fetch_cryptopanic(),
            self._fetch_newsapi(),
        ]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        raw_articles = []
        for res in results:
            if isinstance(res, list):
                raw_articles.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Ошибка при получении новостей из источника: {res}")

        # 2. Дедупликация и сортировка по времени
        unique_articles = self._deduplicate_articles(raw_articles)
        unique_articles.sort(key=lambda x: x.get("published_at"), reverse=True)

        # 3. Обогащение статей полным текстом (первые N статей для экономии ресурсов)
        enrich_tasks = [self._fetch_article_body(article) for article in unique_articles[:self.config.ENRICH_LIMIT]]
        enriched_articles = await asyncio.gather(*enrich_tasks)

        # 4. Валидация и сохранение в кэш
        try:
            validated_articles = [NewsArticle.model_validate(art) for art in enriched_articles]
            await self._cache_articles(validated_articles)
            return validated_articles[:limit]
        except ValidationError as e:
            logger.error(f"Ошибка валидации новостей перед кэшированием: {e}")
            return []

    async def _fetch_cryptopanic(self) -> List[Dict[str, Any]]:
        """Получает новости из API CryptoPanic."""
        if not settings.CRYPTOPANIC_API_KEY:
            logger.warning("Токен CRYPTOPANIC_API_KEY не установлен. Пропуск источника.")
            return []
            
        params = {
            "auth_token": settings.CRYPTOPANIC_API_KEY.get_secret_value(),
            "kind": "news",
            "public": "true",
        }
        try:
            async with http_session() as client:
                response = await client.get(self.config.CRYPTOPANIC_URL, params=params)
                response.raise_for_status()
                data = response.json()

            return [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "source": item.get("source", {}).get("title"),
                    "published_at": parse_datetime(item.get("published_at")),
                }
                for item in data.get("results", [])
            ]
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.error(f"Не удалось получить новости от CryptoPanic: {e}")
            return []

    async def _fetch_newsapi(self) -> List[Dict[str, Any]]:
        """Получает новости из NewsAPI."""
        if not settings.NEWS_API_KEY:
            logger.warning("Ключ NEWS_API_KEY не установлен. Пропуск источника.")
            return []

        params = {
            "q": "crypto OR bitcoin OR ethereum OR blockchain",
            "sortBy": "publishedAt",
            "language": self.config.LANGUAGE,
            "pageSize": self.config.PAGE_SIZE,
            "apiKey": settings.NEWS_API_KEY.get_secret_value(),
        }
        try:
            async with http_session() as client:
                response = await client.get(self.config.NEWSAPI_URL, params=params)
                response.raise_for_status()
                data = response.json()

            return [
                {
                    "id": hashlib.sha1(item.get("url", "").encode()).hexdigest(),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "source": item.get("source", {}).get("name"),
                    "published_at": parse_datetime(item.get("publishedAt")),
                }
                for item in data.get("articles", [])
            ]
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.error(f"Не удалось получить новости от NewsAPI: {e}")
            return []

    async def _fetch_article_body(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Пытается загрузить и очистить полный текст статьи по URL."""
        url = article_data.get("url")
        if not url:
            article_data["body"] = ""
            return article_data
        
        try:
            async with http_session() as client:
                response = await client.get(url, follow_redirects=True, timeout=10.0)
                response.raise_for_status()
                # Используем BeautifulSoup для извлечения текста без HTML-тегов
                soup = BeautifulSoup(response.text, "html.parser")
                # Удаляем скрипты и стили
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()
                
                # Получаем текст и очищаем от лишних пробелов
                text = soup.get_text(separator="\n", strip=True)
                article_data["body"] = "\n".join(line for line in text.splitlines() if line.strip())
        except Exception as e:
            logger.warning(f"Не удалось загрузить тело статьи {url}: {e}")
            article_data["body"] = "" # В случае ошибки оставляем тело пустым
        
        return article_data

    def _deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Удаляет дубликаты новостей по URL."""
        seen_urls = set()
        unique_articles = []
        for article in articles:
            url = article.get("url")
            if url and url not in seen_urls:
                unique_articles.append(article)
                seen_urls.add(url)
        return unique_articles

    async def _cache_articles(self, articles: List[NewsArticle]):
        """Сохраняет список новостей в кэш Redis."""
        try:
            # Сериализуем список Pydantic-моделей в JSON
            data_to_cache = json.dumps([article.model_dump(mode='json') for article in articles])
            await self.redis.set(self.keys.news_cache(), data_to_cache, ex=self.config.CACHE_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Ошибка при сохранении новостей в кэш Redis: {e}")

    async def _get_cached_news(self) -> Optional[List[NewsArticle]]:
        """Получает и валидирует список новостей из кэша Redis."""
        try:
            cached_data = await self.redis.get(self.keys.news_cache())
            if not cached_data:
                return None
            
            # Десериализуем и валидируем каждую новость
            articles_raw = json.loads(cached_data)
            return [NewsArticle.model_validate(item) for item in articles_raw]
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Кэш новостей поврежден или устарел: {e}. Будет выполнен новый запрос.")
            return None
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша новостей из Redis: {e}")
            return None