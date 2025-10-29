# src/bot/services/news_service.py
import asyncio
import json
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.http_client import HttpClient
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle, parse_datetime


class NewsService:
    """Агрегирует, дедуплицирует, валидирует и кэширует новости в Redis."""

    def __init__(self, redis_client: Redis, http_client: HttpClient):
        self.redis = redis_client
        self.http_client = http_client
        self.config = settings.news_service
        self.keys = KeyFactory
        logger.info("Сервис NewsService инициализирован.")

    async def get_all_latest_news(self, limit: int = 30) -> List[NewsArticle]:
        """Основной метод для получения новостей."""
        try:
            cached_news = await self._get_cached_news()
            if cached_news:
                logger.debug(f"Возвращаю {len(cached_news)} новостей из кэша")
                return cached_news[:limit]

            logger.info("Кэш новостей пуст. Запускаю обновление...")
            return await self.update_news_cache(limit=limit)
        except Exception as e:
            logger.exception(f"Критическая ошибка в get_all_latest_news: {e}")
            return []

    async def update_news_cache(self, limit: int = 30) -> List[NewsArticle]:
        """Принудительно обновляет кэш новостей."""
        try:
            tasks = [self._fetch_rss(str(feed)) for feed in self.config.feeds.main_rss_feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            raw_articles = []
            for res in results:
                if isinstance(res, list):
                    raw_articles.extend(res)
                elif isinstance(res, Exception):
                    logger.error(f"Ошибка при получении RSS: {res}")
            
            if not raw_articles:
                logger.warning("Не удалось получить новости ни из одного источника")
                return []
            
            unique_articles = self._deduplicate_articles(raw_articles)
            unique_articles.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

            validated_articles = []
            for art in unique_articles:
                try:
                    validated_articles.append(NewsArticle.model_validate(art))
                except ValidationError as e:
                    logger.warning(f"Пропускаю невалидную статью: {e}")
                    continue
            
            if validated_articles:
                await self._cache_articles(validated_articles)
                logger.success(f"Обновлено {len(validated_articles)} новостей")
            
            return validated_articles[:limit]
        except Exception as e:
            logger.exception(f"Критическая ошибка в update_news_cache: {e}")
            return []
            
    async def _fetch_rss(self, url: str) -> List[Dict[str, Any]]:
        """Получает и парсит новости из RSS-фида."""
        try:
            response_text = await self.http_client.get(url, response_type='text')
            if not response_text:
                logger.warning(f"Пустой ответ от {url}")
                return []
                
            soup = BeautifulSoup(response_text, 'xml')
            items = soup.find_all('item')
            
            if not items:
                logger.warning(f"RSS фид {url} не содержит элементов <item>")
                return []
            
            articles = []
            for item in items[:self.config.news_limit_per_source]:
                try:
                    title_tag = item.find('title')
                    link_tag = item.find('link')
                    pub_date_tag = item.find('pubDate')
                    
                    title = title_tag.text.strip() if title_tag else 'Без заголовка'
                    link = link_tag.text.strip() if link_tag else ''
                    pub_date_str = pub_date_tag.text.strip() if pub_date_tag else ''
                    
                    if not link:
                        continue
                    
                    articles.append({
                        "title": title,
                        "url": link,
                        "source": url.split('/')[2] if '/' in url else url,
                        "timestamp": parse_datetime(pub_date_str),
                    })
                except Exception as e:
                    logger.warning(f"Ошибка парсинга элемента RSS из {url}: {e}")
                    continue
                    
            logger.debug(f"Получено {len(articles)} статей из {url}")
            return articles
        except Exception as e:
            logger.error(f"Не удалось получить новости из RSS {url}: {e}")
            return []

    def _deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Удаляет дубликаты новостей по URL."""
        seen = set()
        unique = []
        for a in articles:
            url = a.get("url")
            if url and url not in seen:
                seen.add(url)
                unique.append(a)
        return unique

    async def _cache_articles(self, articles: List[NewsArticle]):
        """Сохраняет список новостей в кэш Redis."""
        if not articles:
            return
            
        try:
            data = json.dumps([a.model_dump(mode='json') for a in articles], ensure_ascii=False)
            await self.redis.set(
                self.keys.news_deduplication_set(), 
                data, 
                ex=self.config.cache_ttl_seconds
            )
            logger.debug(f"Закэшировано {len(articles)} новостей")
        except Exception as e:
            logger.exception(f"Ошибка при сохранении новостей в кэш Redis: {e}")

    async def _get_cached_news(self) -> Optional[List[NewsArticle]]:
        """Получает и валидирует список новостей из кэша Redis."""
        try:
            data = await self.redis.get(self.keys.news_deduplication_set())
            if not data:
                return None
                
            items = json.loads(data)
            if not isinstance(items, list):
                logger.warning("Неверный формат данных в кэше новостей")
                return None
                
            validated = []
            for item in items:
                try:
                    validated.append(NewsArticle.model_validate(item))
                except ValidationError:
                    continue
                    
            return validated if validated else None
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка декодирования JSON из кэша новостей: {e}")
            return None
        except Exception as e:
            logger.exception(f"Ошибка при чтении кэша новостей из Redis: {e}")
            return None