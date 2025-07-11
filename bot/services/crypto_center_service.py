import json
import logging
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
import aiohttp
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

    @alru_cache(maxsize=2, ttl=3600 * 6)  # Кэшируем на 6 часов
    async def generate_airdrop_alpha(self) -> List[Dict[str, Any]]:
        """
        Генерирует актуальный список Airdrop-проектов с помощью Gemini API.
        """
        logger.info("Generating new Airdrop Alpha using Gemini API...")
        prompt = (
            "Act as a crypto researcher. Identify the top 3 most promising, unreleased projects that are highly likely to have an airdrop in the near future. "
            "For each project, provide a name, a short compelling description, its current status (e.g., 'Active Testnet', 'Confirmed Airdrop'), "
            "a list of 5 concrete actions a user should take to qualify, and a link to an official guide or announcement. "
            "Ensure the information is relevant for the current date. Format the output as a JSON array."
        )
        
        # Схема для структурированного ответа от Gemini
        json_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "name": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "status": {"type": "STRING"},
                    "tasks": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "guide_url": {"type": "STRING"}
                },
                "required": ["id", "name", "description", "status", "tasks", "guide_url"]
            }
        }

        try:
            # ИСПРАВЛЕНО: Используем правильный ключ API
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": json_schema
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return []
                    result = await response.json()
                    
                    text_content = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '[]')
                    parsed_json = json.loads(text_content)
                    logger.info(f"Successfully generated {len(parsed_json)} airdrop opportunities.")
                    return parsed_json

        except Exception as e:
            logger.error(f"An error occurred during Airdrop Alpha generation: {e}")
            return []

    @alru_cache(maxsize=2, ttl=3600 * 6)  # Кэшируем на 6 часов
    async def generate_mining_alpha(self) -> List[Dict[str, Any]]:
        """
        Генерирует актуальные майнинг-сигналы с помощью Gemini API.
        """
        logger.info("Generating new Mining Alpha using Gemini API...")
        prompt = (
            "Act as a mining analyst. Identify the top 3 most relevant and potentially profitable mining opportunities right now, considering different hardware types (ASIC, GPU, CPU). "
            "Focus on emerging trends like DePIN, privacy coins, or new promising algorithms. For each opportunity, provide a name, a short description of why it's relevant now, "
            "the algorithm, recommended hardware, its current status (e.g., 'High Potential', 'Situational'), and a link to an official guide or pool. "
            "Ensure the information is relevant for the current date. Format the output as a JSON array."
        )
        
        json_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "name": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "algorithm": {"type": "STRING"},
                    "hardware": {"type": "STRING"},
                    "status": {"type": "STRING"},
                    "guide_url": {"type": "STRING"}
                },
                "required": ["id", "name", "description", "algorithm", "hardware", "status", "guide_url"]
            }
        }

        try:
            # ИСПРАВЛЕНО: Используем правильный ключ API
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": json_schema
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return []
                    result = await response.json()
                    
                    text_content = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '[]')
                    parsed_json = json.loads(text_content)
                    logger.info(f"Successfully generated {len(parsed_json)} mining opportunities.")
                    return parsed_json

        except Exception as e:
            logger.error(f"An error occurred during Mining Alpha generation: {e}")
            return []

    @alru_cache(maxsize=1, ttl=60 * 15)
    async def fetch_live_feed(self) -> Optional[List[Dict[str, Any]]]:
        """Запрашивает и возвращает свежие новости из внешнего API."""
        logger.info("Fetching fresh crypto news feed...")
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
                    logger.info(f"Successfully fetched {len(data['Data'])} news articles.")
                    return data["Data"][:10]
        except Exception as e:
            logger.error(f"An error occurred while fetching crypto news: {e}")
            return None

    # --- Методы для работы с прогрессом пользователя (остаются без изменений) ---
    
    def _get_user_progress_key(self, user_id: int, airdrop_id: str) -> str:
        return f"user:{user_id}:airdrop:{airdrop_id}:completed_tasks"

    async def get_user_progress(self, user_id: int, airdrop_id: str, all_airdrops: List[Dict[str, Any]]) -> List[int]:
        airdrop = self.get_airdrop_by_id(airdrop_id, all_airdrops)
        if not airdrop: return []
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
            
    def get_airdrop_by_id(self, airdrop_id: str, all_airdrops: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for airdrop in all_airdrops:
            if airdrop['id'] == airdrop_id:
                return airdrop
        return None
