import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

import aiohttp
import redis.asyncio as redis
from async_lru import alru_cache
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz

from bot.config.settings import settings
from bot.utils.helpers import make_request, parse_power
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class AsicService:
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session
        self.LAST_UPDATE_KEY = "asics_last_update_utc"

    def _normalize_name_aggressively(self, name: str) -> str:
        """
        Агрессивно очищает имя ASIC, оставляя только суть модели для надежного сравнения.
        "Bitmain Antminer S19K Pro 110 Th/s" -> "s19kpro110"
        """
        name = re.sub(r'\b(bitmain|antminer|whatsminer|canaan|avalon|jasminer|goldshell|бу)\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(th/s|ths|gh/s|mh/s|ksol|t|g|m)\b', '', name, flags=re.IGNORECASE)
        return re.sub(r'[^a-z0-9]', '', name.lower())

    @alru_cache(maxsize=1, ttl=3600 * settings.asic_cache_update_hours)
    async def update_asics_db(self) -> List[AsicMiner]:
        """
        Главный "Альфа" метод обновления. Загружает данные из всех источников
        параллельно и интеллектуально объединяет их для максимальной полноты.
        """
        logger.info("="*20)
        logger.info("STARTING SCHEDULED ASIC DB UPDATE (INTELLIGENT MERGE LOGIC)")
        logger.info("="*20)
        
        results = await asyncio.gather(
            self._fetch_from_whattomine_api(self.session),
            self._fetch_from_asicminervalue(self.session),
            return_exceptions=True
        )
        
        whattomine_asics = results[0] if isinstance(results[0], list) else []
        asicvalue_asics = results[1] if isinstance(results[1], list) else []
        fallback_asics = [AsicMiner(**data) for data in settings.fallback_asics]

        if not whattomine_asics:
            logger.warning("No ASICs fetched from WhatToMine API.")
        if not asicvalue_asics:
            logger.warning("No ASICs fetched from AsicMinerValue.")
        if not fallback_asics:
            logger.warning("No fallback ASICs available.")

        if not any([whattomine_asics, asicvalue_asics, fallback_asics]):
            logger.error("All data sources returned empty lists. Cache will not be updated.")
            return []

        master_asics = self._intelligent_merge(
            sources=[asicvalue_asics, whattomine_asics, fallback_asics]
        )
        
        if not master_asics:
            logger.error("CRITICAL: All data sources failed to provide any valid data. Cache will not be updated.")
            return []

        final_asics = list(master_asics.values())
        valid_asics = [asic for asic in final_asics if asic.name and asic.profitability is not None]
        
        if not valid_asics:
            logger.error("Merging resulted in no valid ASICs. Cache will not be updated.")
            return []

        logger.info(f"Update successful. Total unique and valid ASICs: {len(valid_asics)}. Caching to Redis.")
        await self._cache_asics_to_redis(valid_asics)
        await self.redis.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
        return sorted(valid_asics, key=lambda x: x.profitability, reverse=True)

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        """
        Создает "мастер-лист" асиков, обогащая его данными из нескольких источников
        с использованием нечеткого сравнения имен.
        """
        master_asics: Dict[str, AsicMiner] = {}
        
        for source_list in sources:
            if not source_list:
                continue
            
            master_keys = list(master_asics.keys())
            
            for asic_to_merge in source_list:
                normalized_to_merge = self._normalize_name_aggressively(asic_to_merge.name)
                if not normalized_to_merge:
                    continue

                best_match = process.extractOne(normalized_to_merge, master_keys, scorer=fuzz.WRatio, score_cutoff=90) if master_keys else None

                if best_match:
                    match_key = best_match[0]
                    existing_asic = master_asics[match_key]
                    
                    # Обогащаем данные, отдавая приоритет более полным
                    if (not existing_asic.power or existing_asic.power == 0) and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if (not existing_asic.hashrate or existing_asic.hashrate.lower() == 'n/a') and asic_to_merge.hashrate:
                        existing_asic.hashrate = asic_to_merge.hashrate
                    if (not existing_asic.algorithm or existing_asic.algorithm.lower() == 'unknown') and asic_to_merge.algorithm:
                        existing_asic.algorithm = asic_to_merge.algorithm
                    if (not existing_asic.efficiency or existing_asic.efficiency.lower() == 'n/a') and asic_to_merge.efficiency:
                        existing_asic.efficiency = asic_to_merge.efficiency
                    if asic_to_merge.profitability is not None:
                        existing_asic.profitability = asic_to_merge.profitability
                else:
                    master_asics[normalized_to_merge] = asic_to_merge
        
        logger.info(f"Intelligent merge complete. Total unique ASICs found: {len(master_asics)}.")
        return master_asics

    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        logger.info(f"Preparing to cache {len(asics)} ASICs to Redis...")
        async with self.redis.pipeline() as pipe:
            old_keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if old_keys:
                logger.info(f"Deleting {len(old_keys)} old ASIC keys from Redis.")
                await pipe.delete(*old_keys)

            cached_count = 0
            for asic in asics:
                model_key = self._normalize_name_aggressively(asic.name)
                redis_key = f"asic_passport:{model_key}"
                
                asic_dict = {
                    "name": asic.name,
                    "profitability": str(asic.profitability or 0.0),
                    "algorithm": asic.algorithm or "N/A",
                    "power": str(asic.power or 0),
                    "hashrate": asic.hashrate or "N/A",
                    "efficiency": asic.efficiency or "N/A"
                }
                pipe.hset(redis_key, mapping=asic_dict)
                cached_count += 1
            
            await pipe.execute()
        logger.info(f"Successfully cached {cached_count} ASICs.")

    async def _fetch_from_whattomine_api(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        try:
            data = await make_request(session, settings.whattomine_asics_url)
            if not data or "asics" not in data:
                logger.warning("No ASIC data returned from WhatToMine API.")
                return []
            asics = []
            for key, asic_data in data["asics"].items():
                try:
                    if "revenue" not in asic_data:
                        continue
                    profitability_str = asic_data.get("revenue", "0").replace("$", "").strip()
                    asics.append(AsicMiner(
                        name=key, profitability=float(profitability_str),
                        algorithm=asic_data.get("algorithm"), power=parse_power(str(asic_data.get("power", 0))),
                        hashrate=asic_data.get("hashrate"), efficiency=None
                    ))
                except (ValueError, TypeError):
                    continue
            logger.info(f"Successfully fetched {len(asics)} ASICs from WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during WhatToMine fetch: {e}")
            return []

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        try:
            html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
            if not html_content:
                logger.warning("No HTML content returned from AsicMinerValue.")
                return []
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', {'id': 'datatable'})
            if not table or not table.find('tbody'):
                logger.warning("No valid table found in AsicMinerValue HTML.")
                return []
            asics = []
            for row in table.tbody.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 6:
                        continue
                    name = cols[1].find('a').text.strip()
                    profitability_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip().replace('W', '').strip()
                    if not name or not profitability_text or not power_text:
                        continue
                    asics.append(AsicMiner(
                        name=name, profitability=float(profitability_text),
                        power=int(power_text), hashrate=cols[2].text.strip(),
                        efficiency=cols[5].text.strip(), algorithm="Unknown"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError):
                    continue
            logger.info(f"Successfully fetched {len(asics)} ASICs from AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during AsicMinerValue fetch: {e}")
            return []
    
    async def get_last_update_time(self) -> Optional[datetime]:
        last_update_iso_bytes = await self.redis.get(self.LAST_UPDATE_KEY)
        if last_update_iso_bytes:
            return datetime.fromisoformat(last_update_iso_bytes.decode('utf-8'))
        return None

    @staticmethod
    def calculate_net_profit(profitability: float, power: int, electricity_cost: float) -> float:
        if power <= 0 or electricity_cost < 0:
            return profitability
        power_kwh_per_day = (power / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        return profitability - daily_cost

    async def get_top_asics(self, count: int = 10, electricity_cost: float = 0.0) -> Tuple[List[AsicMiner], Optional[datetime]]:
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        if not keys:
            logger.warning("No ASIC data found in Redis cache. Attempting to update.")
            await self.update_asics_db()
            keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if not keys:
                logger.error("Redis cache is still empty after update attempt.")
                return [], await self.get_last_update_time()

        pipe = self.redis.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = await pipe.execute()
        
        asics = []
        for data_bytes in results:
            if not data_bytes:
                continue
            try:
                data = {k.decode('utf-8'): v.decode('utf-8') for k, v in data_bytes.items()}
                if 'name' not in data:
                    continue
                name_str = data['name'].strip()
                if not name_str or name_str.lower() == 'unknown':
                    continue
                profitability = float(data.get('profitability', '0.0'))
                power = int(data.get('power', '0'))
                net_profit = self.calculate_net_profit(profitability, power, electricity_cost)
                asics.append(AsicMiner(
                    name=name_str, profitability=net_profit, power=power,
                    algorithm=data.get('algorithm', 'Unknown'),
                    hashrate=data.get('hashrate', 'N/A'),
                    efficiency=data.get('efficiency', 'N/A')
                ))
            except (ValueError, TypeError, KeyError):
                continue
        
        sorted_asics = sorted(asics, key=lambda x: x.profitability, reverse=True)
        last_update_time = await self.get_last_update_time()
        
        return sorted_asics[:count], last_update_time

    async def find_asic_by_query(self, model_query: str) -> Optional[dict]:
        logger.info(f"Processing ASIC query: '{model_query}'")
        normalized_query = self._normalize_name_aggressively(model_query)
        if not normalized_query:
            logger.warning(f"Normalized query for '{model_query}' is empty.")
            return None
        
        all_keys_bytes = [key async for key in self.redis.scan_iter("asic_passport:*")]
        if not all_keys_bytes:
            logger.warning("No ASIC data found in Redis for query.")
            return None
        
        all_keys_str = [key.decode('utf-8').replace('asic_passport:', '') for key in all_keys_bytes]
        logger.debug(f"Normalized query: {normalized_query}, available keys: {all_keys_str}")
        
        best_match = process.extractOne(normalized_query, all_keys_str, scorer=fuzz.WRatio, score_cutoff=80)
        if not best_match:
            logger.warning(f"No match found for query '{model_query}' (normalized: '{normalized_query}')")
            return None
        
        match_key_str = f"asic_passport:{best_match[0]}"
        data_bytes = await self.redis.hgetall(match_key_str)
        return {k.decode('utf-8'): v.decode('utf-8') for k, v in data_bytes.items()}

    async def debug_redis_contents(self):
        """
        Debug function to log all ASIC data stored in Redis.
        """
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        logger.info(f"Found {len(keys)} ASIC keys in Redis: {keys}")
        for key in keys:
            data = await self.redis.hgetall(key)
            logger.info(f"Key {key.decode('utf-8')}: {data}")