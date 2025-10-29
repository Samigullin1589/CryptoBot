# src/bot/services/asic_service.py
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from rapidfuzz import fuzz, process
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.parser_service import ParserService
from bot.utils.keys import KeyFactory
from bot.utils.models import AsicMiner
from bot.utils.redis_lock import LockAcquisitionError, RedisLock
from bot.utils.text_utils import normalize_asic_name


class AsicService:
    """Сервис-оркестратор для управления базой данных ASIC-майнеров."""
    
    def __init__(self, parser_service: ParserService, redis_client: Redis):
        self.redis = redis_client
        self.parser_service = parser_service
        self.config = settings.asic_service
        self.keys = KeyFactory
        self.fallback_path = Path(__file__).parent.parent.parent / self.config.fallback_file_path
        logger.info("Сервис AsicService инициализирован.")

    async def update_asic_list_from_sources(self) -> int:
        """Основной метод обновления базы ASIC."""
        lock_key = self.keys.asics_update_lock()
        try:
            async with RedisLock(self.redis, lock_key, timeout=300, wait_timeout=5):
                logger.info("Блокировка для обновления ASIC успешно получена.")
                return await self._perform_update()
        except LockAcquisitionError:
            logger.warning("Не удалось получить блокировку. Обновление ASIC уже выполняется.")
            return 0
        except Exception as e:
            logger.exception(f"Критическая ошибка во время обновления ASIC: {e}")
            return 0

    async def _perform_update(self) -> int:
        online_sources = await self._fetch_online_sources()
        merged_asics = self._intelligent_merge(online_sources)
        enriched_asics = await self._enrich_asics_with_specs(list(merged_asics.values()))

        if enriched_asics:
            final_asic_list = enriched_asics
            logger.success(f"Успешно обработано {len(final_asic_list)} ASIC из онлайн-источников.")
            await self._create_fallback_backup(final_asic_list)
        else:
            logger.warning("Онлайн-источники недоступны. Загрузка из резервного файла.")
            final_asic_list = self._load_fallback_asics()

        if not final_asic_list:
            logger.critical("Не удалось получить данные ASIC. Обновление отменено.")
            return 0

        await self._store_asics_in_redis(final_asic_list)
        return len(final_asic_list)

    async def _fetch_online_sources(self) -> List[List[AsicMiner]]:
        results = await asyncio.gather(
            self.parser_service.fetch_from_whattomine(),
            self.parser_service.fetch_from_asicminervalue(),
            return_exceptions=True
        )
        return [res for res in results if isinstance(res, list) and res]

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        master_asics: Dict[str, AsicMiner] = {}
        for source_list in sources:
            for asic in source_list:
                norm_name = normalize_asic_name(asic.name)
                if not norm_name:
                    continue

                match = process.extractOne(
                    norm_name,
                    master_asics.keys(),
                    scorer=fuzz.WRatio,
                    score_cutoff=self.config.merge_score_cutoff
                ) if master_asics else None

                if match:
                    existing = master_asics[match[0]]
                    if (not existing.power or existing.power == 0) and asic.power:
                        existing.power = asic.power
                    if not existing.algorithm and asic.algorithm:
                        existing.algorithm = asic.algorithm
                    if asic.profitability is not None:
                        existing.profitability = asic.profitability
                else:
                    master_asics[norm_name] = asic
        return master_asics

    async def _enrich_asics_with_specs(self, asics: List[AsicMiner]) -> List[AsicMiner]:
        specs_db = await self.parser_service.fetch_minerstat_hardware_specs()
        if not specs_db:
            return asics
        
        for asic in asics:
            if not asic.power or not asic.algorithm:
                match = process.extractOne(
                    normalize_asic_name(asic.name),
                    specs_db.keys(),
                    scorer=fuzz.WRatio,
                    score_cutoff=self.config.enrich_score_cutoff
                )
                if match:
                    specs = specs_db[match[0]]
                    if not asic.power and specs.get('power'):
                        asic.power = int(specs['power'])
                    if not asic.algorithm and specs.get('algorithm'):
                        asic.algorithm = specs['algorithm']
        return asics

    async def _store_asics_in_redis(self, asics: List[AsicMiner]):
        temp_key = self.keys.asics_sorted_set() + "_temp"
        pipe = self.redis.pipeline()
        pipe.delete(temp_key)

        mapping = {
            self.keys.asic_hash(normalize_asic_name(a.name)): (a.profitability or 0.0)
            for a in asics
        }
        
        for asic in asics:
            key = self.keys.asic_hash(normalize_asic_name(asic.name))
            pipe.hset(key, mapping=asic.model_dump(mode='json', exclude_none=True))
            pipe.expire(key, self.config.cache_ttl_seconds)

        if mapping:
            pipe.zadd(temp_key, mapping=mapping)
        pipe.set(self.keys.asics_last_update(), datetime.now(timezone.utc).isoformat())
        pipe.rename(temp_key, self.keys.asics_sorted_set())
        
        await pipe.execute()
        logger.info(f"Данные по {len(asics)} ASIC сохранены в Redis.")

    def _load_fallback_asics(self) -> List[AsicMiner]:
        if not self.fallback_path.exists():
            return []
        try:
            with open(self.fallback_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [AsicMiner.model_validate(item) for item in data]
        except Exception as e:
            logger.exception(f"Не удалось загрузить резервный файл ASIC: {e}")
            return []

    async def _create_fallback_backup(self, asics: List[AsicMiner]):
        try:
            def _write_sync():
                with open(self.fallback_path, 'w', encoding='utf-8') as f:
                    json.dump(
                        [a.model_dump(mode='json') for a in asics],
                        f,
                        ensure_ascii=False,
                        indent=2
                    )
            await asyncio.to_thread(_write_sync)
        except Exception as e:
            logger.error(f"Не удалось создать резервную копию ASIC: {e}")

    async def get_top_asics(
        self,
        electricity_cost: float,
        count: int = 50
    ) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """Получает топ ASIC по доходности с учетом стоимости электроэнергии."""
        if not await self.redis.exists(self.keys.asics_sorted_set()):
            await self.update_asic_list_from_sources()

        keys = await self.redis.zrevrange(self.keys.asics_sorted_set(), 0, count - 1)
        if not keys:
            return [], None

        pipe = self.redis.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = await pipe.execute()

        asics = []
        for data in results:
            if not data:
                continue
            asic = AsicMiner.model_validate(data)
            net_profit, daily_cost, gross_profit = self._calculate_net_profit(
                asic.profitability or 0.0,
                asic.power or 0,
                electricity_cost
            )
            asic.net_profit = net_profit
            asic.electricity_cost_per_day = daily_cost
            asic.gross_profit = gross_profit
            asics.append(asic)
        
        asics.sort(key=lambda a: a.net_profit or -999, reverse=True)

        last_update_iso = await self.redis.get(self.keys.asics_last_update())
        last_update = datetime.fromisoformat(last_update_iso) if last_update_iso else None
        
        return asics, last_update

    async def find_asic_by_normalized_name(
        self,
        normalized_name: str,
        electricity_cost: float
    ) -> Optional[AsicMiner]:
        """Находит ASIC по нормализованному имени и рассчитывает доходность."""
        try:
            key = self.keys.asic_hash(normalized_name)
            data = await self.redis.hgetall(key)
            
            if not data:
                logger.warning(f"ASIC с нормализованным именем '{normalized_name}' не найден в Redis")
                return None
            
            asic = AsicMiner.model_validate(data)
            net_profit, daily_cost, gross_profit = self._calculate_net_profit(
                asic.profitability or 0.0,
                asic.power or 0,
                electricity_cost
            )
            asic.net_profit = net_profit
            asic.electricity_cost_per_day = daily_cost
            asic.gross_profit = gross_profit
            
            return asic
        except Exception as e:
            logger.exception(f"Ошибка при поиске ASIC '{normalized_name}': {e}")
            return None

    @staticmethod
    def _calculate_net_profit(
        gross_profit: float,
        power_watts: int,
        electricity_cost: float
    ) -> Tuple[float, float, float]:
        """Рассчитывает чистую прибыль с учетом затрат на электроэнергию."""
        if power_watts <= 0 or electricity_cost < 0:
            return gross_profit, 0.0, gross_profit
        daily_cost = (power_watts / 1000) * 24 * electricity_cost
        return gross_profit - daily_cost, daily_cost, gross_profit