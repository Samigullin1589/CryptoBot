import asyncio
import logging
from typing import List, Dict

import aiohttp
import feedparser
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request, sanitize_html

logger = logging.getLogger(__name__)

class NewsService:
    @alru_cache(maxsize=1, ttl=1800)
    async def fetch_latest_news(self) -> List[Dict]:
        """Получает и объединяет новости из всех RSS-лент."""
        logger.info("Fetching latest news from all RSS feeds...")
        all_news = []
        async with aiohttp.ClientSession() as session:
            tasks = [self._parse_feed(session, url) for url in settings.news_rss_feeds]
            results = await asyncio.gather(*tasks)
        
        for news_list in results:
            all_news.extend(news_list)
            
        # Сортируем все новости по дате публикации
        all_news.sort(key=lambda x: x.get('published_struct'), reverse=True)
        
        # Удаляем дубликаты по заголовку, сохраняя порядок
        unique_news = list({item['title'].lower(): item for item in all_news}.values())
        
        logger.info(f"Fetched {len(unique_news)} unique news items.")
        return unique_news[:5]

    async def _parse_feed(self, session: aiohttp.ClientSession, url: str) -> List[Dict]:
        """Парсит одну RSS-ленту."""
        news_from_feed = []
        try:
            # Используем нашу отказоустойчивую функцию
            text = await make_request(session, url, response_type='text')
            if text:
                feed = feedparser.parse(text)
                for entry in feed.entries:
                    news_from_feed.append({
                        'title': sanitize_html(entry.title),
                        'link': entry.link,
                        'published_struct': getattr(entry, 'published_parsed', None)
                    })
        except Exception as e:
            logger.error(f"Failed to parse RSS feed {url}: {e}")
        return news_from_feed