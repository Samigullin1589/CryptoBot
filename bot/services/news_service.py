# ===============================================================
# Файл: bot/services/news_service.py (НОВЫЙ ФАЙЛ)
# Описание: Специализированный сервис для сбора новостей
# из различных источников (API, RSS). Выделен из
# CryptoCenterService для соответствия принципу единой
# ответственности.
# ===============================================================

import asyncio
import logging
from typing import List, Dict, Any

import aiohttp
import feedparser

from bot.config.settings import settings
from bot.utils.models import NewsArticle
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class NewsService:
    """
    Отвечает за сбор и первичную обработку новостей из различных источников.
    """
    def __init__(self, http_session: aiohttp.ClientSession):
        self.session = http_session

    async def get_latest_articles(self, limit: int = 5) -> List[NewsArticle]:
        """
        Получает список последних новостных статей из основного API.
        """
        logger.info(f"Fetching latest {limit} articles from primary API...")
        try:
            api_url = settings.api_endpoints.crypto_center_news_api_url
            headers = {'Authorization': f'Apikey {settings.api_keys.cryptocompare_api_key}'} if settings.api_keys.cryptocompare_api_key else {}
            
            data = await make_request(self.session, api_url, headers=headers)
            
            if not data or "Data" not in data or not isinstance(data["Data"], list):
                logger.error("Crypto News API response has an unexpected structure.")
                return []
            
            articles_data = data["Data"][:limit]
            articles = [
                NewsArticle(
                    title=article.get('title', 'Без заголовка'),
                    body=article.get('body', ''),
                    url=article.get('url', '')
                ) for article in articles_data
            ]
            logger.info(f"Successfully fetched {len(articles)} articles.")
            return articles
        except Exception as e:
            logger.error(f"An error occurred while fetching crypto news feed: {e}", exc_info=True)
            return []

    async def get_aggregated_news_text(self) -> str:
        """
        Собирает текстовый контент из нескольких источников (API и RSS)
        в единый большой текст для контекстного анализа AI.
        """
        logger.info("Aggregating news text from all sources for AI context...")
        all_text_content = ""

        # 1. Данные из основного API
        api_articles = await self.get_latest_articles(limit=10)
        for article in api_articles:
            all_text_content += f"Title: {article.title}\nBody: {article.body}\n\n"

        # 2. Данные из RSS-лент
        for feed_url in settings.news.alpha_rss_feeds:
            try:
                # feedparser блокирующая библиотека, выполняем в отдельном потоке
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                for entry in feed.entries[:3]:  # Берем 3 свежих из каждой ленты
                    all_text_content += f"Title: {entry.title}\nSummary: {getattr(entry, 'summary', '')}\n\n"
            except Exception as e:
                logger.error(f"Failed to parse RSS feed {feed_url}: {e}")
        
        logger.info(f"Aggregated {len(all_text_content)} characters of text for analysis.")
        return all_text_content

