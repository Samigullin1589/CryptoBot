import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
import aiohttp
import feedparser
from async_lru import alru_cache

from bot.config.settings import settings

logger = logging.getLogger(__name__)

class CryptoCenterService:
    """
    Сервис для управления данными Крипто-Центра, используя AI для генерации контента.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    # --- AI-POWERED, SELF-UPDATING METHODS ---

    async def _gather_live_data(self) -> str:
        """Собирает данные из новостных API и RSS-лент для анализа."""
        logger.info("Gathering live data for AI analysis...")
        all_text_content = ""
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(settings.crypto_center_news_api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get("Data", [])
                        for article in articles[:10]: # Берем 10 свежих
                            all_text_content += f"Title: {article.get('title', '')}\nBody: {article.get('body', '')}\n\n"
        except Exception as e:
            logger.error(f"Failed to fetch from CryptoCompare: {e}")

        for feed_url in settings.alpha_rss_feeds:
            try:
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                for entry in feed.entries[:3]: # Берем 3 свежих из каждой ленты
                    all_text_content += f"Title: {entry.title}\nSummary: {entry.summary}\n\n"
            except Exception as e:
                logger.error(f"Failed to parse RSS feed {feed_url}: {e}")
        
        logger.info(f"Gathered {len(all_text_content)} characters of live data for analysis.")
        return all_text_content


    async def _generate_alpha_from_ai(self, prompt: str, json_schema: Dict) -> List[Dict[str, Any]]:
        """Универсальная функция для запроса к Gemini API."""
        if not settings.gemini_api_key:
            logger.error("GEMINI_API_KEY is not set. Cannot generate AI alpha.")
            return []

        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": json_schema}
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=45) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return []
                    result = await response.json()
                    text_content = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '[]')
                    parsed_json = json.loads(text_content)
                    return parsed_json
        except Exception as e:
            logger.error(f"An error occurred during AI Alpha generation: {e}")
            return []

    @alru_cache(maxsize=2, ttl=3600 * 4)
    async def generate_airdrop_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует актуальный список Airdrop-проектов на русском языке."""
        live_data = await self._gather_live_data()
        if not live_data: return []
        
        prompt = (
            "Действуй как крипто-исследователь. На основе предоставленных ниже новостей и статей, определи 3 самых перспективных проекта без токена, у которых вероятен airdrop. "
            "Для каждого проекта предоставь: 'id' (уникальный идентификатор в одно слово, например 'zksync'), 'name' (название), 'description' (короткое описание, почему это актуально), 'status' (например, 'Активный Testnet'), "
            "'tasks' (список из 3-5 конкретных действий для пользователя) и 'guide_url' (официальная ссылка, если есть). "
            "ВСЯ ТЕКСТОВАЯ ИНФОРМАЦИЯ ДОЛЖНА БЫТЬ НА РУССКОМ ЯЗЫКЕ. Если информации недостаточно, верни пустой массив. Контекст:\n\n"
            f"{live_data}"
        )
        json_schema = { "type": "ARRAY", "items": { "type": "OBJECT", "properties": { "id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "status": {"type": "STRING"}, "tasks": {"type": "ARRAY", "items": {"type": "STRING"}}, "guide_url": {"type": "STRING"} }, "required": ["id", "name", "description", "status", "tasks"] } }
        
        result = await self._generate_alpha_from_ai(prompt, json_schema)
        logger.info(f"AI analysis resulted in {len(result)} airdrop opportunities.")
        return result

    @alru_cache(maxsize=2, ttl=3600 * 4)
    async def generate_mining_alpha(self) -> List[Dict[str, Any]]:
        """Генерирует актуальные майнинг-сигналы на русском языке."""
        live_data = await self._gather_live_data()
        if not live_data: return []
            
        prompt = (
            "Действуй как майнинг-аналитик. На основе предоставленных ниже новостей и статей, определи 3 самых актуальных майнинг-возможности (для ASIC, GPU, или CPU). "
            "Сфокусируйся на новых трендах. Для каждой возможности предоставь: 'id' (уникальный идентификатор), 'name' (название), 'description' (короткое описание актуальности), 'algorithm', 'hardware' (рекомендуемое оборудование), 'status' ('Высокий потенциал', 'Ситуативно') и 'guide_url' (ссылка на гайд или пул). "
            "ВСЯ ТЕКСТОВАЯ ИНФОРМАЦИЯ ДОЛЖНА БЫТЬ НА РУССКОМ ЯЗЫКЕ. Если информации недостаточно, верни пустой массив. Контекст:\n\n"
            f"{live_data}"
        )
        json_schema = { "type": "ARRAY", "items": { "type": "OBJECT", "properties": { "id": {"type": "STRING"}, "name": {"type": "STRING"}, "description": {"type": "STRING"}, "algorithm": {"type": "STRING"}, "hardware": {"type": "STRING"}, "status": {"type": "STRING"}, "guide_url": {"type": "STRING"} }, "required": ["id", "name", "description", "algorithm", "hardware"] } }
        
        result = await self._generate_alpha_from_ai(prompt, json_schema)
        logger.info(f"AI analysis resulted in {len(result)} mining opportunities.")
        return result

    @alru_cache(maxsize=1, ttl=60 * 15)
    async def fetch_live_feed_with_summary(self) -> Optional[List[Dict[str, Any]]]:
        """Запрашивает свежие новости, получает для каждой краткую выжимку от AI и возвращает."""
        logger.info("Fetching fresh crypto news feed for AI analysis...")
        headers = {'Authorization': f'Apikey {settings.cmc_api_key}'} if settings.cmc_api_key else {}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(settings.crypto_center_news_api_url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Crypto News API returned status {response.status}")
                        return None
                    data = await response.json()
                    if "Data" not in data or not isinstance(data["Data"], list):
                        logger.error("Crypto News API response has unexpected structure.")
                        return None
                    
                    news_articles = data["Data"][:5]
                    logger.info(f"Successfully fetched {len(news_articles)} articles for analysis.")

                    analysis_tasks = [self._get_ai_summary(article['body']) for article in news_articles]
                    summaries = await asyncio.gather(*analysis_tasks)
                    
                    for article, summary in zip(news_articles, summaries):
                        article['ai_summary'] = summary
                    return news_articles
        except Exception as e:
            logger.error(f"An error occurred while fetching crypto news feed: {e}")
            return None

    async def _get_ai_summary(self, article_body: str) -> str:
        """Отправляет текст статьи в Gemini для получения краткой выжимки на русском."""
        if not settings.gemini_api_key:
            return "AI-анализ недоступен (ключ не настроен)."
        prompt = (
            "You are a crypto news analyst. Read the following news article and provide a very short, "
            "one-sentence summary in Russian (10-15 words max) that captures the main point. "
            f"Be concise and informative. Here is the article: \n\n{article_body}"
        )
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=20) as response:
                    if response.status != 200: return "Не удалось проанализировать."
                    result = await response.json()
                    summary = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    return summary.strip() if summary else "Не удалось проанализировать."
        except Exception: return "Ошибка анализа."

    # --- Методы для работы с прогрессом пользователя ---
    
    def _get_user_progress_key(self, user_id: int, airdrop_id: str) -> str:
        return f"user:{user_id}:airdrop:{airdrop_id}:completed_tasks"

    async def get_user_progress(self, user_id: int, airdrop_id: str) -> List[int]:
        progress_key = self._get_user_progress_key(user_id, airdrop_id)
        completed_tasks_str = await self.redis.smembers(progress_key)
        return sorted([int(task_idx) for task_idx in completed_tasks_str])

    async def toggle_task_status(self, user_id: int, airdrop_id: str, task_index: int) -> bool:
        progress_key = self._get_user_progress_key(user_id, airdrop_id)
        task_index_str = str(task_index)
        if await self.redis.sismember(progress_key, task_index_str):
            await self.redis.srem(progress_key, task_index_str)
            return False
        else:
            await self.redis.sadd(progress_key, task_index_str)
            return True
            
    # --- НОВЫЙ МЕТОД, КОТОРОГО НЕ ХВАТАЛО ---
    def get_airdrop_by_id(self, airdrop_id: str, all_airdrops: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Ищет аирдроп в предоставленном списке по ID.
        Это необходимо, так как список генерируется динамически.
        """
        for airdrop in all_airdrops:
            # AI должен генерировать 'id', но на всякий случай делаем бэкап из имени
            current_id = airdrop.get('id', airdrop.get('name', '').lower().replace(' ', '_'))
            if current_id == airdrop_id:
                return airdrop
        return None
