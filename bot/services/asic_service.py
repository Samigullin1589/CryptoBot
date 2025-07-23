# ===============================================================
# Файл: bot/services/asic_service.py (ALPHA FIX)
# Описание: Полностью переписана логика обновления. Сервис теперь
# объединяет данные из нескольких источников для максимальной
# полноты информации об ASIC-майнерах.
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

from bot.config.settings import settings
from bot.utils.helpers import make_request, parse_power
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class AsicService:
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session
        self.LAST_UPDATE_KEY = "asics_last_update_utc"

    # --- "АЛЬФА" БЛОК ОБНОВЛЕНИЯ БАЗЫ ДАННЫХ ---
    
    @alru_cache(maxsize=1, ttl=3600 * settings.asic_cache_update_hours)
    async def update_asics_db(self) -> List[AsicMiner]:
        """
        Главный "Альфа" метод обновления. Загружает данные из всех источников
        параллельно и интеллектуально объединяет их для максимальной полноты.
        """
        logger.info("="*20)
        logger.info("STARTING SCHEDULED ASIC DB UPDATE (ALPHA LOGIC)")
        logger.info("="*20)
        
        # 1. Параллельно загружаем данные из всех онлайн-источников
        logger.info("[Step 1/3] Fetching from all online sources in parallel...")
        results = await asyncio.gather(
            self._fetch_from_whattomine_api(self.session),
            self._fetch_from_asicminervalue(self.session),
            return_exceptions=True # Не падаем, если один из источников недоступен
        )
        
        whattomine_asics = results[0] if isinstance(results[0], list) else []
        asicvalue_asics = results[1] if isinstance(results[1], list) else []

        # 2. Интеллектуальное слияние и обогащение данных
        merged_asics = self._merge_and_enrich_asics(whattomine_asics, asicvalue_asics)
        
        # 3. Если онлайн-источники не дали результата, используем локальный резерв
        final_asics = merged_asics
        if not final_asics:
            logger.warning("[Step 2/3] FAILED. All online sources returned no valid data.")
            logger.info("[Step 3/3] Trying final source: Local fallback_asics.json...")
            if settings.fallback_asics and isinstance(settings.fallback_asics, list):
                logger.info(f"Loaded {len(settings.fallback_asics)} ASICs from fallback JSON.")
                final_asics = [AsicMiner(**asic_data) for asic_data in settings.fallback_asics]
            else:
                logger.error("Local fallback_asics.json is empty or invalid.")
                final_asics = []

        if not final_asics:
            logger.error("CRITICAL: All data sources failed completely. Cache will not be updated.")
            return []

        # 4. Фильтрация и сохранение в Redis
        valid_asics = [asic for asic in final_asics if asic.name and asic.profitability is not None]
        if not valid_asics:
            logger.error("All sources failed to provide any valid ASIC entries. Cache will not be updated.")
            return []

        logger.info(f"Update successful. Total valid ASICs found: {len(valid_asics)}. Caching to Redis.")
        await self._cache_asics_to_redis(valid_asics)
        await self.redis.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
        return sorted(valid_asics, key=lambda x: x.profitability, reverse=True)

    def _normalize_name(self, name: str) -> str:
        """Приводит имя ASIC к единому формату для сравнения."""
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def _merge_and_enrich_asics(self, primary_list: List[AsicMiner], enrichment_list: List[AsicMiner]) -> List[AsicMiner]:
        """
        Объединяет два списка ASIC. Берет первый за основу и дополняет данными из второго.
        """
        if not primary_list and not enrichment_list:
            return []
        if not enrichment_list:
            return primary_list
        if not primary_list:
            return enrichment_list

        logger.info(f"Starting enrichment process: {len(primary_list)} primary ASICs, {len(enrichment_list)} enrichment ASICs.")
        
        # Создаем словарь для быстрого поиска по нормализованному имени
        enrichment_map = {self._normalize_name(asic.name): asic for asic in enrichment_list}
        
        enriched_count = 0
        final_list = []

        for primary_asic in primary_list:
            # Проверяем, нужно ли обогащение
            needs_enrichment = not primary_asic.hashrate or primary_asic.hashrate == 'N/A' or not primary_asic.power
            
            if needs_enrichment:
                normalized_name = self._normalize_name(primary_asic.name)
                match = enrichment_map.get(normalized_name)
                
                if match:
                    # Обогащаем только недостающие поля
                    if not primary_asic.hashrate or primary_asic.hashrate == 'N/A':
                        primary_asic.hashrate = match.hashrate
                    if not primary_asic.power:
                        primary_asic.power = match.power
                    if not primary_asic.efficiency:
                        primary_asic.efficiency = match.efficiency
                    
                    enriched_count += 1
                    logger.debug(f"Enriched '{primary_asic.name}' with data from secondary source.")
            
            final_list.append(primary_asic)
        
        logger.info(f"Enrichment complete. {enriched_count} ASICs were updated with additional data.")
        return final_list

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
            if not data or "asics" not in data:
                logger.warning("WTM fetch failed: Invalid data structure or empty response.")
                return []
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
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse WTM ASIC data for key '{key}': {e}. Skipping.")
                    continue
            if not asics:
                logger.warning("WTM parsing resulted in an empty list, though API responded.")
                return []
            logger.info(f"Successfully fetched {len(asics)} ASICs from WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during WhatToMine fetch: {e}")
            return []

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        try:
            html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
            if not html_content:
                logger.warning("AMV fetch failed: Could not download HTML.")
                return []
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', {'id': 'datatable'})
            if not table or not table.find('tbody'):
                logger.warning("AMV parsing failed: Could not find data table. Site structure may have changed.")
                return []
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
                except (AttributeError, ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Could not parse a row on AMV: {e}. Skipping row.")
                    continue
            if not asics:
                logger.warning("AMV parsing resulted in an empty list, though table was found.")
                return []
            logger.info(f"Successfully fetched {len(asics)} ASICs from AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during AsicMinerValue fetch: {e}")
            return []
    
    async def get_last_update_time(self) -> Optional[datetime]:
        last_update_iso_bytes = await self.redis.get(self.LAST_UPDATE_KEY)
        if last_update_iso_bytes:
            last_update_iso = last_update_iso_bytes.decode('utf-8')
            return datetime.fromisoformat(last_update_iso)
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
                if 'name' not in data:
                    logger.warning(f"Skipping invalid entry from Redis cache (no 'name' field): {data}")
                    continue
                name_str = data['name'].strip()
                if not name_str or name_str.lower() == 'unknown':
                    logger.warning(f"Skipping invalid/empty name from Redis cache: {data}")
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
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Could not process cached ASIC data: {data_bytes}. Error: {e}")
                continue
        
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
