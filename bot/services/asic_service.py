# ===============================================================
# Файл: bot/services/asic_service.py (Гениальная альфа-версия)
# Описание: Реализовано автоматическое обогащение данных.
# Сервис сначала получает данные о доходности, а затем, если
# не хватает спецификаций (мощность, алгоритм), он
# автоматически находит их в резервной базе данных MinerStat.
# ===============================================================

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

import aiohttp
import redis.asyncio as redis
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
        # Кэш для справочника спецификаций, чтобы не запрашивать его постоянно
        self._specs_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._specs_cache_time: Optional[datetime] = None

    def _normalize_name_aggressively(self, name: str) -> str:
        """Агрессивно очищает имя ASIC для надежного сравнения."""
        name = re.sub(r'\b(bitmain|antminer|whatsminer|canaan|avalon|jasminer|goldshell|бу)\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(th/s|ths|gh/s|mh/s|ksol|t|g|m)\b', '', name, flags=re.IGNORECASE)
        return re.sub(r'[^a-z0-9]', '', name.lower())

    async def _get_hardware_specs_from_minerstat(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Получает и кэширует полный справочник спецификаций оборудования с MinerStat.
        Это наша "авторитетная база данных" для обогащения.
        """
        now = datetime.now(timezone.utc)
        # Если кэш свежий (меньше 6 часов), используем его
        if self._specs_cache and self._specs_cache_time and (now - self._specs_cache_time).total_seconds() < 3600 * 6:
            logger.info("Using cached MinerStat hardware specs.")
            return self._specs_cache

        logger.info("Fetching fresh hardware specs from MinerStat API...")
        try:
            hardware_data = await make_request(self.session, "https://api.minerstat.com/v2/hardware")
            if not hardware_data or not isinstance(hardware_data, list):
                logger.error("Failed to fetch or invalid format from MinerStat hardware API.")
                return None
            
            # Создаем словарь с нормализованными именами для быстрого поиска
            specs_dict = {
                self._normalize_name_aggressively(hw['name']): {
                    "power": hw.get('power_consumption'),
                    "algorithm": hw.get('algorithm')
                }
                for hw in hardware_data if 'name' in hw
            }
            
            self._specs_cache = specs_dict
            self._specs_cache_time = now
            logger.info(f"Successfully fetched and cached {len(specs_dict)} hardware specs from MinerStat.")
            return specs_dict
        except Exception as e:
            logger.error(f"Error fetching hardware specs from MinerStat: {e}", exc_info=True)
            return None

    async def _enrich_asics_with_specs(self, asics: List[AsicMiner]) -> List[AsicMiner]:
        """
        Гениальная альфа-функция: Обогащает список ASIC недостающими данными.
        """
        logger.info(f"Starting data enrichment for {len(asics)} ASICs...")
        specs_db = await self._get_hardware_specs_from_minerstat()
        if not specs_db:
            logger.warning("No specs database available for enrichment. Returning original data.")
            return asics
            
        enriched_count = 0
        specs_keys = list(specs_db.keys())

        for asic in asics:
            # Обогащаем только если не хватает данных
            if not asic.power or not asic.algorithm or asic.algorithm == "Unknown":
                normalized_name = self._normalize_name_aggressively(asic.name)
                best_match = process.extractOne(normalized_name, specs_keys, scorer=fuzz.WRatio, score_cutoff=92)
                
                if best_match:
                    match_key = best_match[0]
                    specs = specs_db[match_key]
                    
                    if not asic.power and specs.get('power'):
                        asic.power = int(specs['power'])
                    
                    if (not asic.algorithm or asic.algorithm == "Unknown") and specs.get('algorithm'):
                        asic.algorithm = specs['algorithm']
                    
                    enriched_count += 1
                    logger.debug(f"Enriched '{asic.name}' with specs from '{match_key}'.")

        logger.info(f"Enrichment complete. {enriched_count} ASICs were updated with missing specs.")
        return asics

    async def update_asics_db(self) -> List[AsicMiner]:
        logger.info("="*20 + " STARTING SCHEDULED ASIC DB UPDATE " + "="*20)
        
        results = await asyncio.gather(
            self._fetch_from_whattomine_api(self.session),
            self._fetch_from_asicminervalue(self.session),
            return_exceptions=True
        )
        
        whattomine_asics = results[0] if isinstance(results[0], list) else []
        asicvalue_asics = results[1] if isinstance(results[1], list) else []

        if not whattomine_asics and not asicvalue_asics:
            logger.warning("All online sources failed. Using fallback data.")
            final_asics = [AsicMiner(**data) for data in settings.fallback_asics]
        else:
            merged_asics_dict = self._intelligent_merge([whattomine_asics, asicvalue_asics])
            merged_asics_list = list(merged_asics_dict.values())
            
            # --- ГЕНИАЛЬНЫЙ ШАГ: ОБОГАЩАЕМ ДАННЫЕ ---
            enriched_asics = await self._enrich_asics_with_specs(merged_asics_list)
            # ----------------------------------------

            final_asics = enriched_asics

        if not final_asics:
            logger.error("No valid ASIC data from any source. Update failed.")
            return []

        # Финальная сортировка и кэширование
        valid_asics = sorted(final_asics, key=lambda x: x.profitability or 0.0, reverse=True)
        logger.info(f"Update complete. Total valid ASICs: {len(valid_asics)}. Caching to Redis.")
        await self._cache_asics_to_redis(valid_asics)
        await self.redis.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
        return valid_asics

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        master_asics: Dict[str, AsicMiner] = {}
        for source_list in sources:
            if not source_list: continue
            
            master_keys = list(master_asics.keys())
            for asic_to_merge in source_list:
                normalized_to_merge = self._normalize_name_aggressively(asic_to_merge.name)
                if not normalized_to_merge: continue

                best_match = process.extractOne(normalized_to_merge, master_keys, scorer=fuzz.WRatio, score_cutoff=90) if master_keys else None

                if best_match:
                    match_key = best_match[0]
                    existing_asic = master_asics[match_key]
                    # Обновляем данные, если новые "лучше" (т.е. не пустые)
                    if (not existing_asic.power or existing_asic.power == 0) and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if (not existing_asic.hashrate or not re.search(r'[\d.]+', existing_asic.hashrate)) and asic_to_merge.hashrate and re.search(r'[\d.]+', asic_to_merge.hashrate):
                        existing_asic.hashrate = asic_to_merge.hashrate
                    if (not existing_asic.algorithm or existing_asic.algorithm.lower() == 'unknown') and asic_to_merge.algorithm:
                        existing_asic.algorithm = asic_to_merge.algorithm
                    if asic_to_merge.profitability is not None:
                        existing_asic.profitability = asic_to_merge.profitability
                else:
                    master_asics[normalized_to_merge] = asic_to_merge
        
        logger.info(f"Intelligent merge complete. Total unique ASICs: {len(master_asics)}.")
        return master_asics

    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        logger.info(f"Caching {len(asics)} ASICs to Redis...")
        async with self.redis.pipeline() as pipe:
            old_keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if old_keys:
                await pipe.delete(*old_keys)

            for asic in asics:
                model_key = self._normalize_name_aggressively(asic.name)
                redis_key = f"asic_passport:{model_key}"
                # Сохраняем только валидные данные
                asic_dict = {
                    "name": asic.name,
                    "profitability": str(asic.profitability or 0.0),
                    "algorithm": asic.algorithm or "N/A",
                    "power": str(asic.power or 0),
                    "hashrate": asic.hashrate or "N/A",
                    "efficiency": asic.efficiency or "N/A"
                }
                pipe.hset(redis_key, mapping=asic_dict)
            
            await pipe.execute()
        logger.info(f"Successfully cached ASICs.")

    async def _fetch_from_whattomine_api(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        logger.info("Fetching data from WhatToMine API...")
        try:
            data = await make_request(session, settings.whattomine_asics_url)
            if not data or "coins" not in data:
                logger.warning("No valid ASIC data from WhatToMine.")
                return []
            
            asics = []
            for name, details in data["coins"].items():
                try:
                    # WhatToMine API изменился, теперь это словарь, а не список
                    if details.get("tag") and details.get("profitability") is not None:
                        asics.append(AsicMiner(
                            name=details["tag"],
                            profitability=float(details["profitability"]),
                            algorithm=details.get("algorithm"),
                            power=parse_power(str(details.get("power_consumption", 0))),
                            hashrate=str(details.get("hashrate", "N/A")),
                            efficiency=None,
                            source="WhatToMine"
                        ))
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error parsing WhatToMine item '{name}': {e}. Skipping.")
                    continue
            logger.info(f"Successfully fetched {len(asics)} ASICs from WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"Critical error fetching from WhatToMine: {e}", exc_info=True)
            return []

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        logger.info("Fetching data from AsicMinerValue...")
        try:
            html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
            if not html_content:
                logger.warning("No HTML from AsicMinerValue. Skipping.")
                return []
            
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', {'id': 'miners'})
            if not table or not table.find('tbody'):
                logger.warning("No valid table in AsicMinerValue HTML.")
                return []
                
            asics = []
            for row in table.tbody.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 6: continue
                    
                    name = cols[1].find('a').text.strip()
                    profitability_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip().replace('W', '').strip()
                    hashrate_text = cols[2].text.strip()
                    
                    asics.append(AsicMiner(
                        name=name,
                        profitability=float(profitability_text),
                        power=int(power_text),
                        hashrate=hashrate_text,
                        efficiency=cols[5].text.strip(),
                        algorithm="Unknown", # AsicMinerValue не предоставляет алгоритм на главной
                        source="AsicMinerValue"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Error parsing AsicMinerValue row: {e}. Skipping.")
                    continue
            logger.info(f"Successfully fetched {len(asics)} ASICs from AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"Critical error fetching from AsicMinerValue: {e}", exc_info=True)
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
            logger.warning("No ASIC data in Redis. Triggering initial update.")
            await self.update_asics_db()
            keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if not keys:
                logger.error("Redis cache still empty after update. Using hardcoded fallback.")
                return [AsicMiner(**data) for data in settings.fallback_asics][:count], None

        pipe = self.redis.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = await pipe.execute()
        
        asics = []
        for data_bytes in results:
            try:
                if not data_bytes: continue
                data = {k.decode('utf-8'): v.decode('utf-8') for k, v in data_bytes.items()}
                
                profitability = float(data.get('profitability', '0.0'))
                power = int(data.get('power', '0'))
                
                net_profit = self.calculate_net_profit(profitability, power, electricity_cost)
                
                asics.append(AsicMiner(
                    name=data.get('name', 'Unknown'),
                    profitability=net_profit,
                    power=power,
                    algorithm=data.get('algorithm', 'Unknown'),
                    hashrate=data.get('hashrate', 'N/A'),
                    efficiency=data.get('efficiency', 'N/A')
                ))
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error parsing ASIC from Redis cache: {e}. Data: {data_bytes}")
                continue
        
        sorted_asics = sorted(asics, key=lambda x: x.profitability, reverse=True)
        last_update_time = await self.get_last_update_time()
        return sorted_asics[:count], last_update_time

    async def find_asic_by_query(self, model_query: str) -> Optional[dict]:
        logger.info(f"Processing ASIC query: '{model_query}'")
        normalized_query = self._normalize_name_aggressively(model_query)
        if not normalized_query:
            return None
        
        all_keys_bytes = [key async for key in self.redis.scan_iter("asic_passport:*")]
        if not all_keys_bytes:
            logger.warning("No ASIC data in Redis for query.")
            return None
        
        all_keys_str = [key.decode('utf-8').replace('asic_passport:', '') for key in all_keys_bytes]
        
        best_match = process.extractOne(normalized_query, all_keys_str, scorer=fuzz.WRatio, score_cutoff=85)
        if not best_match:
            logger.warning(f"No match found for query '{model_query}'.")
            return None
        
        match_key_str = f"asic_passport:{best_match[0]}"
        data_bytes = await self.redis.hgetall(match_key_str)
        return {k.decode('utf-8'): v.decode('utf-8') for k, v in data_bytes.items()}
