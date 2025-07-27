# ===============================================================
# Файл: bot/services/news_service.py (ПРОДАКШН-ВЕРСЯ 2025)
# Описание: Сервис, отвечающий за сбор "сырых" новостных данных
# из различных источников (API, RSS). Является поставщиком
# контента для других сервисов, например, AIContentService.
# ===============================================================
import asyncio
import logging
from typing import List

import aiohttp
import feedparser

from bot.config.settings import settings
# --- ИСПРАВЛЕНИЕ: Импортируем утилиту из нового, правильного места ---
from bot.utils.http_client import make_request
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.models import NewsArticle

logger = logging.getLogger(__name__)

class NewsService:
    """
    Сервис для сбора новостей из различных API и RSS-лент.
    """
    def __init__(self, http_session: aiohttp.ClientSession):
        self.session = http_session
        self.config = settings.news_service

    async def _fetch_from_cryptocompare(self) -> List[NewsArticle]:
        """Получает новости из API CryptoCompare."""
        headers = {'Authorization': f'Apikey {self.config.cryptocompare_api_key}'} if self.config.cryptocompare_api_key else {}
        data = await make_request(
            self.session, 
            self.config.cryptocompare_url,
            headers=headers
        )
        if not data or "Data" not in data or not isinstance(data["Data"], list):
            logger.warning("Не удалось получить новости от CryptoCompare или структура ответа некорректна.")
            return []
            
        articles = [
            NewsArticle(
                title=article.get('title', 'Без заголовка'),
                body=article.get('body', ''),
                url=article.get('url', ''),
                source='CryptoCompare'
            ) for article in data["Data"][:self.config.news_limit_per_source]
        ]
        logger.info(f"Успешно получено {len(articles)} новостей от CryptoCompare.")
        return articles

    async def _fetch_from_rss(self, feed_url: str) -> List[NewsArticle]:
        """Получает новости из одной RSS-ленты."""
        try:
            # feedparser - синхронная библиотека, запускаем в отдельном потоке
            feed = await asyncio.to_thread(feedparser.parse, feed_url)
            articles = [
                NewsArticle(
                    title=entry.title,
                    body=entry.summary,
                    url=entry.link,
                    source=feed.feed.title
                ) for entry in feed.entries[:self.config.news_limit_per_source]
            ]
            logger.info(f"Успешно получено {len(articles)} новостей из RSS-ленты: {feed.feed.title}.")
            return articles
        except Exception as e:
            logger.error(f"Не удалось обработать RSS-ленту {feed_url}: {e}")
            return []

    async def get_latest_news(self) -> List[NewsArticle]:
        """
        Собирает новости из всех настроенных источников параллельно.
        """
        logger.info("Запуск сбора последних новостей...")
        
        tasks = [self._fetch_from_cryptocompare()]
        tasks.extend([self._fetch_from_rss(url) for url in self.config.rss_feeds])

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Ошибка при сборе новостей: {result}")
        
        logger.info(f"Сбор новостей завершен. Всего получено: {len(all_articles)}.")
        return all_articles
