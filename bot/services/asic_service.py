# ===============================================================
# Файл: bot/services/asic_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Высокопроизводительный сервис для управления базой ASIC.
# ИСПРАВЛЕНИЕ: Конструктор приведен в полное соответствие с DI-контейнером.
# ===============================================================
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

import redis.asyncio as redis
from rapidfuzz import process, fuzz

from bot.config.settings import AsicServiceConfig
from bot.services.parser_service import ParserService
from bot.utils.keys import KeyFactory
from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name
from bot.utils.redis_lock import RedisLock, LockAcquisitionError

logger = logging.getLogger(__name__)

class AsicService:
    """Сервис-оркестратор для управления базой данных ASIC-майнеров."""
    
    # ИСПРАВЛЕНО: Конструктор теперь принимает 'redis'
    def __init__(self, redis: redis.Redis, parser_service: ParserService, config: AsicServiceConfig):
        self.redis = redis
        self.parser_service = parser_service
        self.config = config
        self.keys = KeyFactory
        self._specs_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._specs_cache_time: Optional[datetime] = None

    @staticmethod
    def _calculate_net_profit(gross_profit: float, power_watts: int, electricity_cost: float) -> Tuple[float, float, float]:
        """Рассчитывает чистую прибыль, затраты и грязную прибыль."""
        if power_watts <= 0 or electricity_cost < 0:
            return gross_profit, 0.0, gross_profit

        power_kwh_per_day = (power_watts / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        net_profit = gross_profit - daily_cost
        return net_profit, daily_cost, gross_profit

    async def _get_hardware_specs_from_cache(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Получает и кэширует справочник спецификаций оборудования."""
        cache_lifetime = 3600 * 12 # 12 часов
        if self._specs_cache and self._specs_cache_time and (datetime.now(timezone.utc) - self._specs_cache_time).total_seconds() < cache_lifetime:
            return self._specs_cache
        
        specs_dict = await self.parser_service.fetch_minerstat_hardware_specs()
        if specs_dict:
            self._specs_cache = specs_dict
            self._specs_cache_time = datetime.now(timezone.utc)
        return self._specs_cache

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        master_asics: Dict[str, AsicMiner] = {}
        for source_list in sources:
            if not source_list: continue
            master_keys = list(master_asics.keys())
            for asic_to_merge in source_list:
                normalized_name = normalize_asic_name(asic_to_merge.name)
                if not normalized_name: continue
                best_match = process.extractOne(
                    normalized_name, master_keys, scorer=fuzz.WRatio, score_cutoff=self.config.merge_score_cutoff
                ) if master_keys else None
                if best_match:
                    match_key, _, _ = best_match
                    existing_asic = master_asics[match_key]
                    if (not existing_asic.power or existing_asic.power == 0) and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if (not existing_asic.algorithm) and asic_to_merge.algorithm:
                        existing_asic.algorithm = asic_to_merge.algorithm
                    if asic_to_merge.profitability is not None:
                        existing_asic.profitability = asic_to_merge.profitability
                else:
                    master_asics[normalized_name] = asic_to_merge
        return master_asics

    async def _enrich_asics_with_specs(self, asics: List[AsicMiner]) -> List[AsicMiner]:
        specs_db = await self._get_hardware_specs_from_cache()
        if not specs_db: return asics
        specs_keys = list(specs_db.keys())
        for asic in asics:
            if not asic.power or not asic.algorithm:
                normalized_name = normalize_asic_name(asic.name)
                best_match = process.extractOne(normalized_name, specs_keys, scorer=fuzz.WRatio, score_cutoff=self.config.enrich_score_cutoff)
                if best_match:
                    match_key, _, _ = best_match
                    specs = specs_db[match_key]
                    if not asic.power and specs.get('power'):
                        asic.power = int(specs['power'])
                    if not asic.algorithm and specs.get('algorithm'):
                        asic.algorithm = specs['algorithm']
        return asics

    async def update_asic_list_from_sources(self) -> int:
        logger.info("="*20 + " LAUNCHING ASIC DATABASE UPDATE " + "="*20)
        sources = await asyncio.gather(
            self.parser_service.fetch_from_whattomine(),
            self.parser_service.fetch_from_asicminervalue(),
            return_exceptions=True
        )
        valid_sources = [s for s in sources if isinstance(s, list) and s]
        if not valid_sources:
            logger.error("All ASIC data sources failed. Update aborted.")
            return 0
        merged = self._intelligent_merge(valid_sources)
        enriched = await self._enrich_asics_with_specs(list(merged.values()))
        if not enriched:
            logger.error("No valid ASIC data after merge/enrichment. Update failed.")
            return 0

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.delete(self.keys.asics_sorted_set()) # Используем await
            sorted_set_data = {}
            for asic in enriched:
                if asic.profitability is None: continue
                asic_key = self.keys.asic_hash(normalize_asic_name(asic.name))
                # Используем model_dump для Pydantic v2
                pipe.hset(asic_key, mapping=asic.model_dump(mode='json', exclude={'net_profit', 'gross_profit', 'electricity_cost_per_day'}))
                sorted_set_data[asic_key] = asic.profitability
            if sorted_set_data:
                pipe.zadd(self.keys.asics_sorted_set(), mapping=sorted_set_data)
            pipe.set(self.keys.asics_last_update(), datetime.now(timezone.utc).isoformat())
            await pipe.execute()
        logger.info(f"Update complete. Cached {len(enriched)} ASICs.")
        return len(enriched)

    async def get_top_asics(self, electricity_cost: float, count: int = 50) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """Получает топ ASIC, рассчитывая чистую прибыль для заданной цены э/э."""
        if not await self.redis.exists(self.keys.asics_sorted_set()):
            lock_key = self.keys.asics_update_lock() 
            try:
                async with RedisLock(self.redis, lock_key, timeout=300, wait_timeout=60):
                    if not await self.redis.exists(self.keys.asics_sorted_set()):
                        logger.info("Кэш ASIC отсутствует. Запуск обновления под блокировкой.")
                        await self.update_asic_list_from_sources()
            except LockAcquisitionError: 
                logger.warning("Не удалось получить блокировку для обновления ASIC (Timeout). Ожидаем завершения текущего обновления.")
                await asyncio.sleep(5)

        asic_keys = await self.redis.zrevrange(self.keys.asics_sorted_set(), 0, count - 1)
        if not asic_keys: return [], None

        async with self.redis.pipeline() as pipe:
            for key in asic_keys:
                pipe.hgetall(key) # hgetall не требует await внутри pipeline
            results = await pipe.execute()

        asics_with_profit = []
        for data in results:
            if not data: continue
            # Используем model_validate для Pydantic v2
            asic = AsicMiner.model_validate(data)
            net_profit, daily_cost, gross_profit = self._calculate_net_profit(asic.profitability or 0.0, asic.power or 0, electricity_cost)
            asic.net_profit = net_profit
            asic.electricity_cost_per_day = daily_cost
            asic.gross_profit = gross_profit
            asics_with_profit.append(asic)
        
        asics_with_profit.sort(key=lambda a: a.net_profit, reverse=True)

        last_update_iso = await self.redis.get(self.keys.asics_last_update())
        last_update = datetime.fromisoformat(last_update_iso) if last_update_iso else None
        
        return asics_with_profit, last_update

    async def find_asic_by_normalized_name(self, normalized_name: str, electricity_cost: float) -> Optional[AsicMiner]:
        """Находит ASIC по его нормализованному имени и рассчитывает прибыль."""
        asic_data = await self.redis.hgetall(self.keys.asic_hash(normalized_name))
        if not asic_data: return None
        
        asic = AsicMiner.model_validate(asic_data)
        net_profit, daily_cost, gross_profit = self._calculate_net_profit(asic.profitability or 0.0, asic.power or 0, electricity_cost)
        asic.net_profit = net_profit
        asic.electricity_cost_per_day = daily_cost
        asic.gross_profit = gross_profit
        return asic
