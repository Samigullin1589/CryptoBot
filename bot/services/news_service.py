# =================================================================================
# Файл: bot/services/news_service.py (ФИНАЛЬНАЯ ВЕРСИЯ - С АГРЕГАЦИЕЙ)
# Описание: Динамический сервис для получения новостей из источников.
# ИСПРАВЛЕНИЕ: Добавлен новый метод get_all_latest_news для
#              сбора новостей со всех источников одновременно.
# =================================================================================

from __future__ import annotations
import logging
import json
import asyncio
import feedparser
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
from datetime import datetime
from time import mktime

import aiohttp
import backoff
from bs4 import BeautifulSoup
from redis.asyncio import Redis

from bot.config.settings import NewsServiceConfig
from bot.utils.models import NewsArticle

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ClientResponseError)

class NewsService:
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        config: NewsServiceConfig,
    ):
        self.redis = redis
        self.http_session = http_session
        self.config = config
        
        self.news_feeds: Dict[str, str] = {}
        self.source_names: Dict[str, str] = {}
        
        for url in config.feeds.main_rss_feeds:
            key, name = self._generate_source_info(str(url))
            if key:
                self.news_feeds[key] = str(url)
                self.source_names[key] = name
        
        logger.info(f"Инициализирован NewsService с {len(self.news_feeds)} источниками новостей.")

    @staticmethod
    def _generate_source_info(url: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            key = domain.replace('.', '_').lower()
            name = domain.split('.')[-2].capitalize()
            return key, name
        except Exception as e:
            logger.error(f"Не удалось сгенерировать информацию об источнике из URL '{url}': {e}")
            return None, None

    def get_all_sources(self) -> Dict[str, str]:
        return self.source_names

    def _get_cache_key(self, source_key: str) -> str:
        return f"cache:news:v3:{source_key}"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, logger=logger)
    async def _fetch_feed_content(self, url: str) -> Optional[str]:
        logger.info(f"Загрузка новостной ленты с: {url}")
        async with self.http_session.get(url, timeout=15) as response:
            response.raise_for_status()
            return await response.text()

    def _parse_feed(self, feed_content: str, source_name: str) -> List[NewsArticle]:
        parsed_feed = feedparser.parse(feed_content)
        articles = []
        for entry in parsed_feed.entries[:self.config.news_limit_per_source]:
            published_timestamp = 0
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_timestamp = int(mktime(entry.published_parsed))

            articles.append(NewsArticle(
                title=entry.title.strip(),
                url=entry.link.strip(),
                body=entry.get('summary', ''),
                source=source_name,
                timestamp=published_timestamp
            ))
        return articles

    async def get_latest_news(self, source_key: str) -> Optional[List[NewsArticle]]:
        if source_key not in self.news_feeds:
            logger.error(f"Запрошен неизвестный источник новостей: {source_key}")
            return None

        cache_key = self._get_cache_key(source_key)
        if cached_news := await self.redis.get(cache_key):
            logger.info(f"Новости для '{source_key}' найдены в кэше.")
            news_data = json.loads(cached_news)
            return [NewsArticle.model_validate(article) for article in news_data]

        try:
            feed_url = self.news_feeds[source_key]
            feed_content = await self._fetch_feed_content(feed_url)
            if not feed_content:
                return None
            
            source_name = self.source_names.get(source_key, "Unknown")
            articles = self._parse_feed(feed_content, source_name)
            
            articles_to_cache = [article.model_dump(mode='json') for article in articles]
            await self.redis.set(cache_key, json.dumps(articles_to_cache), ex=self.config.cache_ttl_seconds)
            
            logger.info(f"Успешно загружено и закэшировано {len(articles)} новостей для '{source_key}'.")
            return articles

        except Exception as e:
            logger.error(f"Не удалось получить новости для '{source_key}': {e}", exc_info=True)
            return None

    async def get_all_latest_news(self) -> List[NewsArticle]:
        """
        [НОВЫЙ МЕТОД] Асинхронно собирает новости со всех источников,
        объединяет их и сортирует по дате.
        """
        logger.info("Сбор новостей со всех источников...")
        tasks = [self.get_latest_news(source_key) for source_key in self.news_feeds.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_articles = []
        for res in results:
            if isinstance(res, list):
                all_articles.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Ошибка при сборе новостей из одного из источников: {res}")
        
        # Сортируем все новости по времени публикации (от новых к старым)
        all_articles.sort(key=lambda x: x.timestamp, reverse=True)
        
        logger.info(f"Собрано {len(all_articles)} новостей со всех источников.")
        return all_articles