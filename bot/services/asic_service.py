# ===============================================================
# Файл: bot/services/asic_service.py (ФИНАЛЬНАЯ АЛЬФА-ВЕРСИЯ)
# Описание: Полностью переписана логика обновления. Сервис теперь
# использует нечеткое сравнение строк (rapidfuzz) для
# интеллектуального объединения данных из всех источников.
# ===============================================================
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

import aiohttp
import redis.asyncio as redis
from async_lru import alru_cache
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz # <-- Импортируем для "Альфа" сопоставления

from bot.config.settings import settings
from bot.utils.helpers import make_request, parse_power
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class AsicService:
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session
        self.LAST_UPDATE_KEY = "asics_last_update_utc"

    def _normalize_name(self, name: str) -> str:
        """Приводит имя ASIC к единому формату для сравнения."""
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
        
        # 1. Параллельно загружаем данные из всех источников
        logger.info("Fetching from all sources in parallel...")
        results = await asyncio.gather(
            self._fetch_from_whattomine_api(self.session),
            self._fetch_from_asicminervalue(self.session),
            return_exceptions=True
        )
        
        whattomine_asics = results[0] if isinstance(results[0], list) else []
        asicvalue_asics = results[1] if isinstance(results[1], list) else []
        fallback_asics = [AsicMiner(**data) for data in settings.fallback_asics]

        # 2. Интеллектуальное слияние с использованием fuzzy matching
        master_asics = self._intelligent_merge(
            primary_source=asicvalue_asics,
            sources_to_merge=[whattomine_asics, fallback_asics]
        )
        
        if not master_asics:
            logger.error("CRITICAL: All data sources failed to provide any valid data. Cache will not be updated.")
            return []

        # 3. Фильтрация и сохранение в Redis
        final_asics = list(master_asics.values())
        valid_asics = [asic for asic in final_asics if asic.name and asic.profitability is not None]
        
        if not valid_asics:
            logger.error("Merging resulted in no valid ASICs. Cache will not be updated.")
            return []

        logger.info(f"Update successful. Total unique and valid ASICs: {len(valid_asics)}. Caching to Redis.")
        await self._cache_asics_to_redis(valid_asics)
        await self.redis.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
        return sorted(valid_asics, key=lambda x: x.profitability, reverse=True)

    def _intelligent_merge(self, primary_source: List[AsicMiner], sources_to_merge: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        """
        Создает "мастер-лист" асиков, обогащая его данными из нескольких источников
        с использованием нечеткого сравнения имен.
        """
        master_asics: Dict[str, AsicMiner] = {}
        
        # Сначала наполняем мастер-лист основным источником
        for asic in primary_source:
            normalized_name = self._normalize_name(asic.name)
            master_asics[normalized_name] = asic
        
        logger.info(f"Created master list with {len(master_asics)} ASICs from primary source.")

        master_keys = list(master_asics.keys())
        
        for source in sources_to_merge:
            if not source: continue
            
            enriched_count = 0
            newly_added_count = 0
            
            for asic_to_merge in source:
                normalized_to_merge = self._normalize_name(asic_to_merge.name)
                
                # Ищем лучшее совпадение в мастер-листе
                best_match = process.extractOne(normalized_to_merge, master_keys, scorer=fuzz.WRatio, score_cutoff=85)

                if best_match:
                    match_key = best_match[0]
                    existing_asic = master_asics[match_key]
                    
                    # Обогащаем данные, отдавая приоритет более полным
                    if not existing_asic.power and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if not existing_asic.hashrate or existing_asic.hashrate == 'N/A':
                        existing_asic.hashrate = asic_to_merge.hashrate
                    if (not existing_asic.algorithm or existing_asic.algorithm == 'Unknown') and asic_to_merge.algorithm:
                         existing_asic.algorithm = asic_to_merge.algorithm
                    
                    enriched_count += 1
                else:
                    # Если совпадений не найдено, это новый асик
                    master_asics[normalized_to_merge] = asic_to_merge
                    master_keys.append(normalized_to_merge) # Обновляем список ключей для поиска
                    newly_added_count += 1

            logger.info(f"Merged source. Enriched: {enriched_count}, Newly added: {newly_added_count}.")
            
        return master_asics

    # ... (остальные методы остаются без изменений: _cache_asics_to_redis, _fetch_..., get_top_asics и т.д.) ...
    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        logger.info(f"Preparing to cache {len(asics)} ASICs to Redis...")
        async with self.redis.pipeline() as pipe:
            old_keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if old_keys:
                logger.info(f"Deleting {len(old_keys)} old ASIC keys from Redis.")
                await pipe.delete(*old_keys)

            cached_count = 0
            for asic in asics:
                model_key = self._normalize_name(asic.name)
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
            if not data or "asics" not in data: return []
            asics = []
            for key, asic_data in data["asics"].items():
                try:
                    if "revenue" not in asic_data: continue
                    profitability_str = asic_data.get("revenue", "0").replace("$", "").strip()
                    asics.append(AsicMiner(
                        name=key, profitability=float(profitability_str),
                        algorithm=asic_data.get("algorithm"), power=parse_power(str(asic_data.get("power", 0))),
                        hashrate=asic_data.get("hashrate"), efficiency=None
                    ))
                except (ValueError, TypeError): continue
            logger.info(f"Successfully fetched {len(asics)} ASICs from WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during WhatToMine fetch: {e}")
            return []

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        try:
            html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
            if not html_content: return []
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', {'id': 'datatable'})
            if not table or not table.find('tbody'): return []
            asics = []
            for row in table.tbody.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 6: continue
                    name = cols[1].find('a').text.strip()
                    profitability_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip().replace('W', '').strip()
                    if not name or not profitability_text or not power_text: continue
                    asics.append(AsicMiner(
                        name=name, profitability=float(profitability_text),
                        power=int(power_text), hashrate=cols[2].text.strip(),
                        efficiency=cols[5].text.strip(), algorithm="Unknown"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError): continue
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
        if power <= 0 or electricity_cost < 0: return profitability
        power_kwh_per_day = (power / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        return profitability - daily_cost

    async def get_top_asics(self, count: int = 10, electricity_cost: float = 0.0) -> Tuple[List[AsicMiner], Optional[datetime]]:
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        if not keys:
            logger.info("ASIC cache is empty. Forcing database update.")
            await self.update_asics_db()
            keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if not keys:
                logger.error("Failed to populate cache even after forced update.")
                return [], await self.get_last_update_time()

        pipe = self.redis.pipeline()
        for key in keys: pipe.hgetall(key)
        results = await pipe.execute()
        
        asics = []
        for data_bytes in results:
            if not data_bytes: continue
            try:
                data = {k.decode('utf-8'): v.decode('utf-8') for k, v in data_bytes.items()}
                if 'name' not in data: continue
                name_str = data['name'].strip()
                if not name_str or name_str.lower() == 'unknown': continue
                profitability = float(data.get('profitability', '0.0'))
                power = int(data.get('power', '0'))
                net_profit = self.calculate_net_profit(profitability, power, electricity_cost)
                asics.append(AsicMiner(
                    name=name_str, profitability=net_profit, power=power,
                    algorithm=data.get('algorithm', 'Unknown'),
                    hashrate=data.get('hashrate', 'N/A'),
                    efficiency=data.get('efficiency', 'N/A')
                ))
            except (ValueError, TypeError, KeyError): continue
        
        sorted_asics = sorted(asics, key=lambda x: x.profitability, reverse=True)
        last_update_time = await self.get_last_update_time()
        
        return sorted_asics[:count], last_update_time

    async def find_asic_by_query(self, model_query: str) -> Optional[dict]:
        normalized_query = self._normalize_name(model_query)
        if not normalized_query: return None
        keys_bytes = [key async for key in self.redis.scan_iter("asic_passport:*")]
        for key_bytes in keys_bytes:
            key_str = key_bytes.decode('utf-8')
            if normalized_query in key_str.replace('asic_passport:', ''):
                data_bytes = await self.redis.hgetall(key_str)
                return {k.decode('utf-8'): v.decode('utf-8') for k, v in data_bytes.items()}
        return None
