import logging
import asyncio
import feedparser
import aiohttp
from typing import List, Dict
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class NewsService:
    @alru_cache(maxsize=1, ttl=1800)  # Кэш на 30 минут
    async def get_latest_news(self) -> List[Dict]:
        """Асинхронно собирает новости со всех RSS-лент."""
        logger.info("Сбор новостей из RSS-лент...")
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_feed(session, url) for url in settings.news_rss_feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_news = []
        seen_links = set()
        for res in results:
            if isinstance(res, list):
                for item in res:
                    if item['link'] not in seen_links:
                        all_news.append(item)
                        seen_links.add(item['link'])

        # Сортируем по дате публикации, если она есть
        all_news.sort(key=lambda x: x.get('published_parsed'), reverse=True)
        logger.info(f"Собрано {len(all_news)} уникальных новостей.")
        return all_news

    async def _fetch_feed(self, session: aiohttp.ClientSession, url: str) -> List[Dict]:
        """Получает и парсит одну RSS-ленту."""
        xml_data = await make_request(session, url, response_type='text')
        if not xml_data or not isinstance(xml_data, str):
            logger.warning(f"Не удалось получить данные для RSS-ленты: {url}")
            return []

        feed = feedparser.parse(xml_data)
        return [{'title': entry.title, 'link': entry.link, 'published_parsed': entry.get('published_parsed')} for entry in feed.entries]