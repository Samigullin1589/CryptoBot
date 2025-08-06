# bot/services/news_service.py
# =================================================================================
# Файл: bot/services/news_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - АДАПТИРОВАННАЯ)
# Описание: Отказоустойчивый сервис для сбора новостей, адаптированный
# для работы с единой системой настроек.
# =================================================================================
import asyncio
import logging
import hashlib
from typing import List, Optional

import aiohttp
import backoff
import feedparser
import redis.asyncio as redis
from aiogram import Bot

# ИСПРАВЛЕНО: Импортируем единый объект настроек
from bot.config.settings import settings
from bot.utils.keys import KeyFactory
from bot.utils.models import NewsArticle
from bot.utils.text_utils import normalize_asic_name, sanitize_html

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, TimeoutError)

class NewsService:
    """Сервис для сбора и дедупликации новостей из различных источников."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        http_session: aiohttp.ClientSession,
    ):
        self.redis = redis_client
        self.session = http_session
        # ИСПРАВЛЕНО: Все настройки берутся из единого объекта
        self.settings = settings
        self.keys = KeyFactory

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3)
    async def _fetch(self, url: str, headers: Optional[dict] = None) -> Optional[dict]:
        """Выполняет отказоустойчивый HTTP-запрос."""
        async with self.session.get(url, headers=headers, timeout=15) as response:
            response.raise_for_status()
            return await response.json()

    async def _fetch_from_cryptocompare(self) -> List[NewsArticle]:
        """Получает новости из API CryptoCompare."""
        api_key = self.settings.CRYPTOCOMPARE_API_KEY
        api_url = self.settings.endpoints.crypto_center_news_api_url

        if not api_key or not api_url:
            logger.warning("CryptoCompare API key или URL не заданы. Пропуск источника новостей.")
            return []

        headers = {'Authorization': f'Apikey {api_key.get_secret_value()}'}
        try:
            data = await self._fetch(str(api_url), headers=headers)
            if not data or "Data" not in data or not isinstance(data["Data"], list):
                logger.warning("Не удалось получить новости от CryptoCompare.")
                return []
            
            return [
                NewsArticle(
                    title=article.get('title', 'Без заголовка'),
                    body=article.get('body', ''),
                    url=article.get('url', ''),
                    source='CryptoCompare',
                    timestamp=int(article.get('published_on', 0))
                ) for article in data["Data"]
            ]
        except Exception as e:
            logger.error(f"Ошибка при получении новостей от CryptoCompare: {e}")
            return []

    async def _fetch_from_rss(self, feed_url: str) -> List[NewsArticle]:
        """Получает новости из одной RSS-ленты."""
        try:
            async with self.session.get(feed_url, timeout=15) as response:
                if response.status != 200: return []
                content = await response.text()
            
            feed = await asyncio.to_thread(feedparser.parse, content)
            return [
                NewsArticle(
                    title=entry.title,
                    body=getattr(entry, 'summary', ''),
                    url=entry.link,
                    source=feed.feed.title,
                    timestamp=int(entry.get('published_parsed', (0,))[0])
                ) for entry in feed.entries
            ]
        except Exception as e:
            logger.error(f"Не удалось обработать RSS-ленту {feed_url}: {e}")
            return []

    async def get_latest_news(self) -> List[NewsArticle]:
        """
        Собирает новости из всех источников и отфильтровывает дубликаты.
        """
        logger.info("Запуск сбора последних новостей...")
        
        tasks = [self._fetch_from_cryptocompare()]
        all_feeds = self.settings.news_service.feeds.main_rss_feeds + self.settings.news_service.feeds.alpha_rss_feeds
        for url in all_feeds:
            tasks.append(self._fetch_from_rss(str(url)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        unique_articles = []
        seen_hashes = set()
        
        dedup_key = self.keys.news_deduplication_set()
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Ошибка при сборе новостей: {result}")
                continue
            
            for article in result:
                title_hash = hashlib.sha1(normalize_asic_name(article.title).encode()).hexdigest()[:16]
                if title_hash in seen_hashes:
                    continue
                
                is_new = await self.redis.sadd(dedup_key, title_hash)
                if is_new:
                    unique_articles.append(article)
                    seen_hashes.add(title_hash)
        
        logger.info(f"Сбор новостей завершен. Уникальных: {len(unique_articles)}.")
        return sorted(unique_articles, key=lambda x: x.timestamp, reverse=True)

    async def send_news_digest(self, bot: Bot, chat_id: int):
        """Формирует и отправляет дайджест новостей."""
        latest_news = await self.get_latest_news()
        if not latest_news:
            logger.info("Нет новых новостей для отправки.")
            return

        news_to_send = latest_news[:self.settings.news_service.news_limit_per_source]
        
        message_parts = ["📰 <b>Свежий дайджест новостей:</b>\n"]
        for article in news_to_send:
            message_parts.append(f"\n- <a href='{article.url}'>{sanitize_html(article.title)}</a> (<i>{sanitize_html(article.source)}</i>)")

        try:
            await bot.send_message(chat_id, "".join(message_parts), disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Не удалось отправить дайджест новостей в чат {chat_id}: {e}")

