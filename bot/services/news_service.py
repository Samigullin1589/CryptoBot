# =================================================================================
# Файл: bot/services/news_service.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025)
# Описание: Динамический сервис для получения новостей из источников,
# определенных в конфигурации, а не в коде.
# =================================================================================

from __future__ import annotations
import logging
import json
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

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
        
        # --- ДИНАМИЧЕСКАЯ ИНИЦИАЛИЗАЦИЯ ИСТОЧНИКОВ ИЗ КОНФИГУРАЦИИ ---
        self.news_feeds: Dict[str, str] = {}
        self.source_names: Dict[str, str] = {}
        
        # Обрабатываем основные ленты
        for url in config.feeds.main_rss_feeds:
            key, name = self._generate_source_info(str(url))
            if key:
                self.news_feeds[key] = str(url)
                self.source_names[key] = name
        
        logger.info(f"Инициализирован NewsService с {len(self.news_feeds)} источниками новостей.")

    @staticmethod
    def _generate_source_info(url: str) -> Tuple[Optional[str], Optional[str]]:
        """Генерирует ключ и читаемое имя из URL."""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            # Создаем ключ (например, 'forklog_com') и имя (например, 'Forklog')
            key = domain.replace('.', '_').lower()
            name = domain.split('.')[-2].capitalize()
            return key, name
        except Exception as e:
            logger.error(f"Не удалось сгенерировать информацию об источнике из URL '{url}': {e}")
            return None, None

    def get_all_sources(self) -> Dict[str, str]:
        """Возвращает словарь {ключ: имя} для всех настроенных источников."""
        return self.source_names

    def _get_cache_key(self, source_key: str) -> str:
        return f"cache:news:v2:{source_key}"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, logger=logger)
    async def _fetch_feed(self, url: str) -> Optional[str]:
        """Загружает RSS-ленту с ретраями."""
        logger.info(f"Загрузка новостной ленты с: {url}")
        async with self.http_session.get(url, timeout=10) as response:
            response.raise_for_status()
            return await response.text()

    def _parse_feed(self, feed_content: str) -> List[NewsArticle]:
        """Парсит XML-контент RSS-ленты и возвращает список статей."""
        soup = BeautifulSoup(feed_content, 'xml')
        items = soup.find_all('item', limit=self.config.news_limit_per_source)
        articles = []
        for item in items:
            title = item.title.text.strip() if item.title else "Без заголовка"
            link = item.link.text.strip() if item.link else ""
            pub_date_tag = item.find('pubDate')
            pub_date = pub_date_tag.text if pub_date_tag else None
            
            articles.append(NewsArticle(title=title, url=link, published_at=pub_date))
        return articles

    async def get_latest_news(self, source_key: str) -> Optional[List[NewsArticle]]:
        """
        Получает последние новости из указанного источника.
        Сначала проверяет кэш, затем запрашивает и парсит ленту.
        """
        if source_key not in self.news_feeds:
            logger.error(f"Запрошен неизвестный источник новостей: {source_key}")
            return None

        cache_key = self._get_cache_key(source_key)
        cached_news = await self.redis.get(cache_key)
        if cached_news:
            logger.info(f"Новости для '{source_key}' найдены в кэше.")
            news_data = json.loads(cached_news)
            return [NewsArticle.model_validate(article) for article in news_data]

        try:
            feed_url = self.news_feeds[source_key]
            feed_content = await self._fetch_feed(feed_url)
            if not feed_content:
                return None
            
            articles = self._parse_feed(feed_content)
            
            articles_to_cache = [article.model_dump(mode='json') for article in articles]
            await self.redis.set(cache_key, json.dumps(articles_to_cache), ex=self.config.cache_ttl_seconds)
            
            logger.info(f"Успешно загружено и закэшировано {len(articles)} новостей для '{source_key}'.")
            return articles

        except Exception as e:
            logger.error(f"Не удалось получить новости для '{source_key}': {e}", exc_info=True)
            return None
