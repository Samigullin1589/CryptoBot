import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings

BASE_DIR = Path(__file__).parent.parent.parent
logger = logging.getLogger(__name__)

class CryptoCenterService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._opportunities = self._load_opportunities_from_file()

    def _load_opportunities_from_file(self) -> Dict[str, List[Dict[str, Any]]]:
        file_path = BASE_DIR / "data" / "alpha_opportunities.json"
        default_data = {"airdrops": [], "mining_signals": []}
        if not file_path.exists():
            return default_data
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading alpha_opportunities.json: {e}")
            return default_data

    @alru_cache(maxsize=1, ttl=60 * 15)
    async def fetch_live_feed(self) -> Optional[List[Dict[str, Any]]]:
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

    def get_all_airdrops(self) -> List[Dict[str, Any]]:
        return self._opportunities.get("airdrops", [])
    
    def get_all_mining_signals(self) -> List[Dict[str, Any]]:
        return self._opportunities.get("mining_signals", [])
    
    def get_airdrop_by_id(self, airdrop_id: str) -> Optional[Dict[str, Any]]:
        for airdrop in self.get_all_airdrops():
            if airdrop['id'] == airdrop_id:
                return airdrop
        return None

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