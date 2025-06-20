# bot/services/news_service.py
import asyncio
import logging
from typing import List, Dict

import aiohttp
import feedparser
from cachetools import cached, TTLCache

# Импорты для новой структуры
from bot.config.settings import settings
from bot.utils.helpers import make_request, sanitize_html

logger = logging.getLogger(__name__)

class NewsService:
    def __init__(self):
        """
        Сервис для получения и кэширования новостей из RSS-лент.
        """
        self.cache = TTLCache(maxsize=1, ttl=1800) # Кэш на 30 минут

    async def _parse_feed(self, session: aiohttp.ClientSession, url: str) -> List[Dict]:
        """Парсит одну RSS-ленту и возвращает список новостей."""
        news_from_feed = []
        try:
            text = await make_request(session, url, response_type='text')
            if text:
                feed = feedparser.parse(text)
                for entry in feed.entries:
                    news_from_feed.append({
                        'title': sanitize_html(entry.title),
                        'link': entry.link,
                        'published': getattr(entry, 'published_parsed', None)
                    })
        except Exception as e:
            logger.warning(f"Failed to parse RSS feed {url}", extra={'error': str(e)})
        return news_from_feed

    @cached(cache=lambda self: self.cache)
    async def fetch_latest_news(self) -> List[Dict]:
        """
        Асинхронно загружает новости со всех RSS-лент, объединяет,
        сортирует и возвращает 5 самых свежих.
        """
        logger.info("Fetching latest news from all RSS feeds...")
        all_news = []
        async with aiohttp.ClientSession() as session:
            tasks = [self._parse_feed(session, url) for url in settings.news_rss_feeds]
            results = await asyncio.gather(*tasks)
        
        for news_list in results:
            all_news.extend(news_list)
            
        # Сортируем все новости по дате публикации (от свежих к старым)
        # Учитываем, что 'published' может отсутствовать
        all_news.sort(key=lambda x: x['published'] or (0,), reverse=True)
        
        # Удаляем дубликаты по заголовку, сохраняя порядок
        unique_news = list({item['title'].lower(): item for item in all_news}.values())
        
        logger.info(f"Fetched {len(unique_news)} unique news items.")
        return unique_news[:5]

