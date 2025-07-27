# ===============================================================
# Файл: bot/services/asic_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Сервис-оркестратор для управления базой данных
# ASIC-майнеров. Отвечает за получение данных от парсеров,
# их слияние, обогащение, кэширование и предоставление
# другим частям приложения.
# ===============================================================
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

import aiohttp
import redis.asyncio as redis
from rapidfuzz import process, fuzz

from bot.config.settings import settings
from bot.services.parser_service import ParserService
# --- ИСПРАВЛЕНИЕ: Импортируем утилиту из нового, правильного места ---
from bot.utils.http_client import make_request
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name

logger = logging.getLogger(__name__)

class AsicService:
    """
    Сервис-оркестратор для управления базой данных ASIC-майнеров.
    """
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.parser_service = ParserService(http_session)
        self.config = settings.asic_service
        # Внутренний кэш в памяти для справочника спецификаций, чтобы не запрашивать его постоянно
        self._specs_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._specs_cache_time: Optional[datetime] = None

    async def _get_hardware_specs_from_minerstat(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Получает и кэширует полный справочник спецификаций оборудования с MinerStat.
        Это наша "авторитетная база данных" для обогащения недостающих данных.
        """
        now = datetime.now(timezone.utc)
        cache_lifetime = self.config.specs_cache_lifetime_hours * 3600
        
        if self._specs_cache and self._specs_cache_time and (now - self._specs_cache_time).total_seconds() < cache_lifetime:
            logger.info("Использую кэшированные спецификации оборудования из памяти.")
            return self._specs_cache

        logger.info("Обновляю справочник спецификаций оборудования с MinerStat API...")
        try:
            hardware_data = await make_request(self.session, self.config.minerstat_hardware_url)
            if not hardware_data or not isinstance(hardware_data, list):
                logger.error("Не удалось получить или неверный формат от MinerStat hardware API.")
                return None
            
            specs_dict = {
                normalize_asic_name(hw['name']): { "power": hw.get('power_consumption'), "algorithm": hw.get('algorithm') }
                for hw in hardware_data if 'name' in hw
            }
            
            self._specs_cache = specs_dict
            self._specs_cache_time = now
            logger.info(f"Успешно получено и кэшировано {len(specs_dict)} спецификаций с MinerStat.")
            return specs_dict
        except Exception as e:
            logger.error(f"Ошибка при получении спецификаций с MinerStat: {e}", exc_info=True)
            return None

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        """
        Интеллектуально объединяет списки ASIC'ов из разных источников в один,
        используя нечеткий поиск для сопоставления и обогащения данных.
        """
        master_asics: Dict[str, AsicMiner] = {}
        for source_list in sources:
            if not source_list: continue
            
            master_keys = list(master_asics.keys())
            for asic_to_merge in source_list:
                normalized_to_merge = normalize_asic_name(asic_to_merge.name)
                if not normalized_to_merge: continue

                best_match = process.extractOne(
                    normalized_to_merge, master_keys, scorer=fuzz.WRatio, score_cutoff=self.config.merge_score_cutoff
                ) if master_keys else None

                if best_match:
                    match_key = best_match[0]
                    existing_asic = master_asics[match_key]
                    # Обновляем данные, если новые "лучше" (т.е. не пустые)
                    if (not existing_asic.power or existing_asic.power == 0) and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if (not existing_asic.algorithm or existing_asic.algorithm.lower() == 'unknown') and asic_to_merge.algorithm:
                        existing_asic.algorithm = asic_to_merge.algorithm
                    if asic_to_merge.profitability is not None:
                        existing_asic.profitability = asic_to_merge.profitability
                else:
                    master_asics[normalized_to_merge] = asic_to_merge
        
        logger.info(f"Интеллектуальное слияние завершено. Уникальных ASIC'ов: {len(master_asics)}.")
        return master_asics

    async def _enrich_asics_with_specs(self, asics: List[AsicMiner]) -> List[AsicMiner]:
        """Обогащает список ASIC недостающими данными (мощность, алгоритм) из справочника."""
        logger.info(f"Начинаю обогащение данных для {len(asics)} ASIC'ов...")
        specs_db = await self._get_hardware_specs_from_minerstat()
        if not specs_db:
            logger.warning("Справочник спецификаций недоступен. Возвращаю исходные данные.")
            return asics
            
        enriched_count = 0
        specs_keys = list(specs_db.keys())

        for asic in asics:
            # Обогащаем только если не хватает ключевых данных
            if not asic.power or not asic.algorithm or asic.algorithm == "Unknown":
                normalized_name = normalize_asic_name(asic.name)
                best_match = process.extractOne(
                    normalized_name, specs_keys, scorer=fuzz.WRatio, score_cutoff=self.config.enrich_score_cutoff
                )
                
                if best_match:
                    match_key, _, _ = best_match
                    specs = specs_db[match_key]
                    if not asic.power and specs.get('power'):
                        asic.power = int(specs['power'])
                    if (not asic.algorithm or asic.algorithm == "Unknown") and specs.get('algorithm'):
                        asic.algorithm = specs['algorithm']
                    enriched_count += 1
        
        logger.info(f"Обогащение завершено. Обновлено {enriched_count} ASIC'ов.")
        return asics

    async def update_asics_db(self) -> None:
        """
        Основной метод. Запускает полный цикл обновления базы ASIC:
        1. Парсит данные с источников.
        2. Объединяет и обогащает их.
        3. Сохраняет результат в кэш Redis.
        """
        logger.info("="*20 + " ЗАПУСК ОБНОВЛЕНИЯ БАЗЫ ASIC " + "="*20)
        
        results = await asyncio.gather(
            self.parser_service.fetch_from_whattomine(),
            self.parser_service.fetch_from_asicminervalue(),
            return_exceptions=True
        )
        
        whattomine_asics, asicvalue_asics = results[0], results[1]
        
        if isinstance(whattomine_asics, Exception): whattomine_asics = []
        if isinstance(asicvalue_asics, Exception): asicvalue_asics = []

        if not whattomine_asics and not asicvalue_asics:
            logger.warning("Все онлайн-источники парсинга не ответили. Использую резервные данные.")
            final_asics = [AsicMiner(**data) for data in settings.fallback_asics]
        else:
            merged_asics_dict = self._intelligent_merge([whattomine_asics, asicvalue_asics])
            enriched_asics = await self._enrich_asics_with_specs(list(merged_asics_dict.values()))
            final_asics = enriched_asics

        if not final_asics:
            logger.error("Нет валидных данных об ASIC ни из одного источника. Обновление не удалось.")
            return

        sorted_asics = sorted(final_asics, key=lambda x: x.profitability or 0.0, reverse=True)
        
        logger.info(f"Обновление завершено. Всего валидных ASIC'ов: {len(sorted_asics)}. Кэширую в Redis.")
        await self.redis.set(self.config.cache_key, json.dumps([asic.model_dump() for asic in sorted_asics], default=str))
        await self.redis.set(self.config.last_update_key, datetime.now(timezone.utc).isoformat())

    async def get_all_asics(self) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """
        Получает полный список ASIC'ов из кэша Redis. Если кэш пуст, запускает обновление.
        """
        cached_data = await self.redis.get(self.config.cache_key)
        
        if not cached_data:
            logger.warning("Кэш ASIC в Redis пуст. Запускаю принудительное обновление.")
            await self.update_asics_db()
            cached_data = await self.redis.get(self.config.cache_key)
            if not cached_data:
                logger.error("Кэш все еще пуст после обновления. Использую резервные данные из файла.")
                fallback_asics = [AsicMiner(**data) for data in settings.fallback_asics]
                return fallback_asics, None

        asics = [AsicMiner.model_validate(item) for item in json.loads(cached_data)]
        
        last_update_iso = await self.redis.get(self.config.last_update_key)
        last_update_time = datetime.fromisoformat(last_update_iso) if last_update_iso else None
        
        return asics, last_update_time

    async def find_asic_by_query(self, query: str) -> Optional[AsicMiner]:
        """
        Находит наиболее подходящий ASIC в базе по текстовому запросу.
        """
        logger.info(f"Выполняю поиск ASIC по запросу: '{query}'")
        normalized_query = normalize_asic_name(query)
        if not normalized_query: return None
        
        all_asics, _ = await self.get_all_asics()
        if not all_asics: return None
        
        choices = {normalize_asic_name(asic.name): asic for asic in all_asics}
        
        best_match = process.extractOne(
            normalized_query, choices.keys(), scorer=fuzz.WRatio, score_cutoff=self.config.search_score_cutoff
        )
        
        if not best_match:
            logger.warning(f"Не найдено совпадений для запроса '{query}'.")
            return None
        
        match_key, _, _ = best_match
        return choices[match_key]
