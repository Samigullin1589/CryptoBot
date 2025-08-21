# bot/services/asic_service.py
# Дата обновления: 19.08.2025
# Версия: 2.0.0
# Описание: Высокопроизводительный и отказоустойчивый сервис для управления
# базой данных ASIC-майнеров, их характеристиками и расчетом прибыльности.

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
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import AsicMiner
from bot.utils.redis_lock import LockAcquisitionError, RedisLock
from bot.utils.text_utils import normalize_asic_name


class AsicService:
    """
    Сервис-оркестратор для управления базой данных ASIC-майнеров.
    - Агрегирует данные из нескольких источников.
    - Обогащает их техническими характеристиками.
    - Обеспечивает отказоустойчивость за счет резервных копий.
    - Кэширует данные в Redis для высокой производительности.
    - Рассчитывает чистую прибыльность с учетом стоимости электроэнергии.
    """

    def __init__(self, parser_service: ParserService):
        self.redis: Redis = get_redis_client()
        self.parser_service = parser_service
        self.config = settings.ASIC
        self.keys = KeyFactory
        self.fallback_path = Path(__file__).parent.parent.parent / self.config.FALLBACK_FILE_PATH
        logger.info("Сервис AsicService инициализирован.")

    async def update_asic_list_from_sources(self) -> int:
        """
        Основной метод обновления базы ASIC. Выполняется под блокировкой,
        чтобы избежать одновременного запуска несколькими процессами.
        """
        lock_key = self.keys.asics_update_lock()
        try:
            async with RedisLock(self.redis, lock_key, timeout=300, wait_timeout=5):
                logger.info("Блокировка для обновления ASIC успешно получена. Начинаю обновление...")
                return await self._perform_update()
        except LockAcquisitionError:
            logger.warning("Не удалось получить блокировку. Обновление ASIC уже выполняется другим процессом.")
            return 0
        except Exception as e:
            logger.exception(f"Критическая ошибка во время обновления ASIC: {e}")
            return 0

    async def _perform_update(self) -> int:
        """
        Выполняет шаги по обновлению: загрузка, слияние, обогащение и сохранение данных.
        """
        # 1. Асинхронно получаем данные из всех онлайн-источников
        online_sources = await self._fetch_online_sources()
        
        # 2. Интеллектуально объединяем и обогащаем данные
        merged_asics = self._intelligent_merge(online_sources)
        enriched_asics = await self._enrich_asics_with_specs(list(merged_asics.values()))

        # 3. Определяем финальный список для сохранения
        if enriched_asics:
            final_asic_list = enriched_asics
            logger.success(f"Успешно загружено и обработано {len(final_asic_list)} ASIC из онлайн-источников.")
            await self._create_fallback_backup(final_asic_list)
        else:
            logger.warning("Все онлайн-источники недоступны. Попытка загрузки из резервного файла.")
            final_asic_list = self._load_fallback_asics()

        if not final_asic_list:
            logger.critical("Не удалось получить данные ASIC ни из онлайн-источников, ни из резервного файла. Обновление отменено.")
            return 0

        # 4. Сохраняем данные в Redis по "безопасной" схеме
        await self._store_asics_in_redis(final_asic_list)
        return len(final_asic_list)

    async def _fetch_online_sources(self) -> List[List[AsicMiner]]:
        """Асинхронно запрашивает данные у всех парсеров."""
        results = await asyncio.gather(
            self.parser_service.fetch_from_whattomine(),
            self.parser_service.fetch_from_asicminervalue(),
            return_exceptions=True
        )
        valid_sources = []
        for i, res in enumerate(results):
            if isinstance(res, list) and res:
                valid_sources.append(res)
            elif isinstance(res, Exception):
                logger.error(f"Источник #{i+1} не ответил: {res}")
        return valid_sources

    def _intelligent_merge(self, sources: List[List[AsicMiner]]) -> Dict[str, AsicMiner]:
        """
        Объединяет списки ASIC из разных источников в один мастер-список,
        дополняя недостающие данные.
        """
        master_asics: Dict[str, AsicMiner] = {}
        for source_list in sources:
            for asic_to_merge in source_list:
                normalized_name = normalize_asic_name(asic_to_merge.name)
                if not normalized_name:
                    continue

                master_keys = list(master_asics.keys())
                best_match = process.extractOne(
                    normalized_name, master_keys, scorer=fuzz.WRatio, score_cutoff=self.config.MERGE_SCORE_CUTOFF
                ) if master_keys else None

                if best_match:
                    match_key, _, _ = best_match
                    existing_asic = master_asics[match_key]
                    # Обновляем поля, если они пустые у существующей модели
                    if (not existing_asic.power or existing_asic.power == 0) and asic_to_merge.power:
                        existing_asic.power = asic_to_merge.power
                    if not existing_asic.algorithm and asic_to_merge.algorithm:
                        existing_asic.algorithm = asic_to_merge.algorithm
                    if asic_to_merge.profitability is not None:
                        existing_asic.profitability = asic_to_merge.profitability
                else:
                    master_asics[normalized_name] = asic_to_merge
        return master_asics

    async def _enrich_asics_with_specs(self, asics: List[AsicMiner]) -> List[AsicMiner]:
        """Обогащает данные ASIC информацией из справочника спецификаций."""
        specs_db = await self.parser_service.fetch_minerstat_hardware_specs()
        if not specs_db:
            logger.warning("Не удалось получить справочник спецификаций, обогащение пропущено.")
            return asics
            
        specs_keys = list(specs_db.keys())
        for asic in asics:
            if not asic.power or not asic.algorithm:
                normalized_name = normalize_asic_name(asic.name)
                best_match = process.extractOne(
                    normalized_name, specs_keys, scorer=fuzz.WRatio, score_cutoff=self.config.ENRICH_SCORE_CUTOFF
                )
                if best_match:
                    match_key, _, _ = best_match
                    specs = specs_db[match_key]
                    if not asic.power and specs.get('power'):
                        asic.power = int(specs['power'])
                    if not asic.algorithm and specs.get('algorithm'):
                        asic.algorithm = specs['algorithm']
        return asics

    async def _store_asics_in_redis(self, asics: List[AsicMiner]):
        """
        Сохраняет список ASIC в Redis, используя временные ключи и атомарную замену,
        чтобы избежать состояния, когда данных нет.
        """
        temp_sorted_set_key = self.keys.asics_sorted_set() + "_temp"
        
        pipe = self.redis.pipeline()
        pipe.delete(temp_sorted_set_key) # Очищаем временный ключ на всякий случай

        sorted_set_data = {}
        for asic in asics:
            if asic.profitability is None:
                continue
            
            normalized_name = normalize_asic_name(asic.name)
            asic_key = self.keys.asic_hash(normalized_name)
            
            # Сохраняем данные каждого ASIC в отдельный HASH
            pipe.hset(asic_key, mapping=asic.model_dump(mode='json', exclude_none=True))
            pipe.expire(asic_key, self.config.CACHE_TTL_SECONDS)
            
            # Готовим данные для сортированного списка (ключ -> профит)
            sorted_set_data[asic_key] = asic.profitability

        if sorted_set_data:
            pipe.zadd(temp_sorted_set_key, mapping=sorted_set_data)
        
        pipe.set(self.keys.asics_last_update(), datetime.now(timezone.utc).isoformat())
        
        # Атомарно переименовываем временный ключ в основной
        pipe.rename(temp_sorted_set_key, self.keys.asics_sorted_set())
        
        await pipe.execute()
        logger.info(f"Данные по {len(asics)} ASIC успешно сохранены в Redis.")

    def _load_fallback_asics(self) -> List[AsicMiner]:
        """Загружает список ASIC из локального резервного JSON-файла."""
        if not self.fallback_path.exists():
            logger.error(f"Резервный файл ASIC не найден: {self.fallback_path}")
            return []
        try:
            with open(self.fallback_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            asics = [AsicMiner.model_validate(item) for item in data]
            logger.warning(f"Загружено {len(asics)} ASIC из резервного файла.")
            return asics
        except Exception as e:
            logger.exception(f"Критическая ошибка: не удалось загрузить резервный файл ASIC: {e}")
            return []

    async def _create_fallback_backup(self, asics: List[AsicMiner]):
        """Создает локальную резервную копию списка ASIC."""
        try:
            # Выполняем I/O операцию в отдельном потоке, чтобы не блокировать event loop
            def _write_backup():
                with open(self.fallback_path, 'w', encoding='utf-8') as f:
                    # Преобразуем список объектов Pydantic в список словарей
                    json.dump([asic.model_dump(mode='json') for asic in asics], f, ensure_ascii=False, indent=2)
            
            await asyncio.to_thread(_write_backup)
            logger.info(f"Резервная копия {len(asics)} ASIC успешно создана в {self.fallback_path}")
        except Exception as e:
            logger.error(f"Не удалось создать резервную копию ASIC: {e}")

    async def get_top_asics(self, electricity_cost: float, count: int = 50) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """
        Получает топ ASIC из кэша, рассчитывая чистую прибыль для заданной цены э/э.
        Если кэш пуст, инициирует обновление.
        """
        if not await self.redis.exists(self.keys.asics_sorted_set()):
            logger.warning("Кэш ASIC пуст. Запускаю первоначальное обновление...")
            await self.update_asic_list_from_sources()

        asic_keys = await self.redis.zrevrange(self.keys.asics_sorted_set(), 0, count - 1)
        if not asic_keys:
            return [], None

        pipe = self.redis.pipeline()
        for key in asic_keys:
            pipe.hgetall(key)
        results = await pipe.execute()

        asics_with_profit = []
        for data in results:
            if not data:
                continue
            asic = AsicMiner.model_validate(data)
            net_profit, daily_cost, gross_profit = self._calculate_net_profit(
                asic.profitability or 0.0, asic.power or 0, electricity_cost
            )
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
        if not asic_data:
            return None
        
        asic = AsicMiner.model_validate(asic_data)
        net_profit, daily_cost, gross_profit = self._calculate_net_profit(
            asic.profitability or 0.0, asic.power or 0, electricity_cost
        )
        asic.net_profit = net_profit
        asic.electricity_cost_per_day = daily_cost
        asic.gross_profit = gross_profit
        return asic

    @staticmethod
    def _calculate_net_profit(gross_profit: float, power_watts: int, electricity_cost: float) -> Tuple[float, float, float]:
        """Рассчитывает чистую прибыль, суточные затраты и валовую прибыль."""
        if power_watts <= 0 or electricity_cost < 0:
            return gross_profit, 0.0, gross_profit

        power_kwh_per_day = (power_watts / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        net_profit = gross_profit - daily_cost
        return net_profit, daily_cost, gross_profit