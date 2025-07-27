# ===============================================================
# Файл: bot/services/asic_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный сервис. Отвечает за
# оркестрацию: получение данных от ParserService, их слияние,
# обогащение и сверхэффективное кэширование в Redis.
# ===============================================================

import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any

import aiohttp
import redis.asyncio as redis
from rapidfuzz import process, fuzz

from bot.config.settings import settings
from bot.services.parser_service import ParserService
from bot.utils.helpers import make_request
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class AsicService:
    """
    Сервис-оркестратор для управления базой данных ASIC-майнеров.
    Отвечает за слияние, обогащение и кэширование данных.
    """
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session
        self.parser_service = ParserService(http_session)
        
        # --- Redis Keys ---
        self.CACHE_KEY = "cache:asics_db"
        self.LAST_UPDATE_KEY = "cache:asics_last_update_utc"
        
        # --- In-memory cache for specs ---
        self._specs_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._specs_cache_time: Optional[datetime] = None

    def _normalize_name_aggressively(self, name: str) -> str:
        """Агрессивно очищает имя ASIC для надежного сравнения."""
        name = re.sub(r'\b(bitmain|antminer|whatsminer|canaan|avalon|jasminer|goldshell|бу|used)\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(th/s|ths|gh/s|mh/s|ksol|t|g|m)\b', '', name, flags=re.IGNORECASE)
        return re.sub(r'[^a-z0-9]', '', name.lower())

    async def _get_specs_from_minerstat(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Получает и кэширует справочник спецификаций с MinerStat."""
        now = datetime.now(timezone.utc)
        if self._specs_cache and self._specs_cache_time and (now - self._specs_cache_time) < timedelta(hours=6):
            return self._specs_cache

        logger.info("Fetching fresh hardware specs from MinerStat API...")
        try:
            hardware_data = await make_request(self.session, settings.api_endpoints.minerstat_api_base + "/hardware")
            if not isinstance(hardware_data, list):
                logger.error("Failed to fetch or invalid format from MinerStat hardware API.")
                return None
            
            specs_dict = {
                self._normalize_name_aggressively(hw['name']): {"power": hw.get('power_consumption'), "algorithm": hw.get('algorithm')}
                for hw in hardware_data if 'name' in hw
            }
            
            self._specs_cache = specs_dict
            self._specs_cache_time = now
            logger.info(f"Successfully fetched and cached {len(specs_dict)} hardware specs from MinerStat.")
            return specs_dict
        except Exception as e:
            logger.error(f"Error fetching hardware specs from MinerStat: {e}", exc_info=True)
            return None

    async def _enrich_asics(self, asics: List[AsicMiner]) -> List[AsicMiner]:
        """Обогащает список ASIC недостающими данными (мощность, алгоритм)."""
        logger.info(f"Starting data enrichment for {len(asics)} ASICs...")
        specs_db = await self._get_specs_from_minerstat()
        if not specs_db:
            logger.warning("No specs database available for enrichment. Returning original data.")
            return asics
            
        enriched_count = 0
        specs_keys = list(specs_db.keys())

        for asic in asics:
            if not asic.power or not asic.algorithm or asic.algorithm == "Unknown":
                normalized_name = self._normalize_name_aggressively(asic.name)
                best_match = process.extractOne(normalized_name, specs_keys, scorer=fuzz.WRatio, score_cutoff=92)
                
                if best_match:
                    match_key, _, _ = best_match
                    specs = specs_db[match_key]
                    
                    if not asic.power and specs.get('power'):
                        asic.power = int(specs['power'])
                    if (not asic.algorithm or asic.algorithm == "Unknown") and specs.get('algorithm'):
                        asic.algorithm = specs['algorithm']
                    
                    enriched_count += 1
                    logger.debug(f"Enriched '{asic.name}' with specs from '{match_key}'.")

        logger.info(f"Enrichment complete. {enriched_count} ASICs were updated.")
        return asics

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> List[AsicMiner]:
        """Интеллектуально сливает данные из нескольких источников."""
        master_asics: Dict[str, AsicMiner] = {}
        for source_list in sources:
            if not source_list: continue
            
            for asic_to_merge in source_list:
                normalized_to_merge = self._normalize_name_aggressively(asic_to_merge.name)
                if not normalized_to_merge: continue

                # Пытаемся найти точное совпадение
                if normalized_to_merge in master_asics:
                    match_key = normalized_to_merge
                else: # Если нет, ищем нечеткое
                    master_keys = list(master_asics.keys())
                    best_match = process.extractOne(normalized_to_merge, master_keys, scorer=fuzz.WRatio, score_cutoff=90) if master_keys else None
                    match_key = best_match[0] if best_match else None

                if match_key:
                    existing_asic = master_asics[match_key]
                    # Обновляем поля, если новые данные лучше
                    if (not existing_asic.power or existing_asic.power == 0) and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if (not existing_asic.algorithm or existing_asic.algorithm.lower() == 'unknown') and asic_to_merge.algorithm:
                        existing_asic.algorithm = asic_to_merge.algorithm
                    if asic_to_merge.profitability is not None:
                        existing_asic.profitability = asic_to_merge.profitability
                else:
                    master_asics[normalized_to_merge] = asic_to_merge
        
        logger.info(f"Intelligent merge complete. Total unique ASICs: {len(master_asics)}.")
        return list(master_asics.values())

    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        """Кэширует весь список ASIC как одну JSON-строку для максимальной производительности."""
        logger.info(f"Caching {len(asics)} ASICs to Redis as a single JSON blob.")
        try:
            # Преобразуем список объектов Pydantic в список словарей
            asics_dict_list = [asic.model_dump() for asic in asics]
            json_data = json.dumps(asics_dict_list, ensure_ascii=False)
            
            async with self.redis.pipeline() as pipe:
                pipe.set(self.CACHE_KEY, json_data)
                pipe.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
                await pipe.execute()
            logger.info("Successfully cached ASICs to Redis.")
        except Exception as e:
            logger.error(f"Failed to cache ASICs to Redis: {e}", exc_info=True)

    async def update_asics_db(self) -> List[AsicMiner]:
        """Полный цикл обновления базы ASIC: парсинг, слияние, обогащение, кэширование."""
        logger.info("="*20 + " STARTING ASIC DB UPDATE " + "="*20)
        
        results = await asyncio.gather(
            self.parser_service.fetch_whattomine_data(),
            self.parser_service.fetch_asicminervalue_data(),
            return_exceptions=True
        )
        
        # Проверяем, что результаты не являются ошибками
        whattomine_asics = results[0] if isinstance(results[0], list) else []
        asicvalue_asics = results[1] if isinstance(results[1], list) else []

        if not whattomine_asics and not asicvalue_asics:
            logger.warning("All online sources failed. Using fallback data.")
            final_asics = [AsicMiner(**data) for data in settings.fallback_asics]
        else:
            merged_asics = self._intelligent_merge([whattomine_asics, asicvalue_asics])
            enriched_asics = await self._enrich_asics(merged_asics)
            final_asics = enriched_asics

        if not final_asics:
            logger.error("No valid ASIC data from any source. Update failed.")
            return []

        await self._cache_asics_to_redis(final_asics)
        return final_asics

    @staticmethod
    def calculate_net_profit(gross_profit: float, power: Optional[int], electricity_cost: float) -> float:
        """Рассчитывает чистую прибыль."""
        if not power or power <= 0 or electricity_cost < 0:
            return gross_profit
        power_kwh_per_day = (power / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        return gross_profit - daily_cost

    async def get_all_asics_from_cache(self) -> List[AsicMiner]:
        """Получает и десериализует полный список ASIC из кэша Redis."""
        cached_json = await self.redis.get(self.CACHE_KEY)
        if not cached_json:
            logger.warning("ASIC cache is empty. Triggering force update.")
            return await self.update_asics_db()
        
        try:
            asics_dict_list = json.loads(cached_json)
            return [AsicMiner(**data) for data in asics_dict_list]
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode ASIC cache from Redis: {e}. Triggering force update.")
            return await self.update_asics_db()

    async def get_top_asics(self, count: int, electricity_cost: float, sort_by: str = 'profitability') -> Tuple[List[AsicMiner], Optional[datetime]]:
        """
        Возвращает топ ASIC-майнеров, отсортированных по чистой прибыли.
        Данные берутся из единого кэша, что обеспечивает высокую производительность.
        """
        all_asics = await self.get_all_asics_from_cache()
        if not all_asics:
             return [], await self.get_last_update_time()

        # Рассчитываем чистую прибыль для каждого ASIC
        for asic in all_asics:
            # Перезаписываем profitability чистым значением для сортировки
            asic.profitability = self.calculate_net_profit(asic.profitability or 0.0, asic.power, electricity_cost)

        # Сортируем по выбранному критерию
        if sort_by == 'efficiency' and all(asic.efficiency for asic in all_asics):
             # Сортировка по эффективности (меньше - лучше)
            all_asics.sort(key=lambda x: float(x.efficiency.split()[0]) if x.efficiency else float('inf'))
        else: # По умолчанию сортируем по прибыльности
            all_asics.sort(key=lambda x: x.profitability or 0.0, reverse=True)

        last_update_time = await self.get_last_update_time()
        return all_asics[:count], last_update_time

    async def find_asic_by_query(self, model_query: str) -> Optional[AsicMiner]:
        """Находит один ASIC по нечеткому запросу в кэшированном списке."""
        all_asics = await self.get_all_asics_from_cache()
        if not all_asics:
            return None
        
        # Создаем словарь для поиска: {оригинальное_имя: объект_AsicMiner}
        choices = {asic.name: asic for asic in all_asics}
        
        best_match = process.extractOne(model_query, choices.keys(), scorer=fuzz.WRatio, score_cutoff=85)
        
        if not best_match:
            logger.info(f"No ASIC found for query '{model_query}' with score > 85.")
            return None
            
        match_name, _, _ = best_match
        logger.info(f"Found ASIC '{match_name}' for query '{model_query}'.")
        return choices[match_name]

    async def get_last_update_time(self) -> Optional[datetime]:
        """Получает время последнего успешного обновления из Redis."""
        last_update_iso_bytes = await self.redis.get(self.LAST_UPDATE_KEY)
        if last_update_iso_bytes:
            return datetime.fromisoformat(last_update_iso_bytes.decode('utf-8'))
        return None
