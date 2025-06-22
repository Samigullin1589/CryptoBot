import json
import logging
import aiohttp
from typing import List, Optional
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.models import AsicMiner
# Импортируем нашу новую функцию
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class AsicService:
    @alru_cache(maxsize=1, ttl=settings.asic_cache_update_hours * 3600)
    async def get_profitable_asics(self) -> List[AsicMiner]:
        """
        Возвращает отсортированный список самых прибыльных ASIC-майнеров.
        Данные кэшируются.
        """
        logger.info("Обновление кэша ASIC-майнеров...")
        miners = []
        async with aiohttp.ClientSession() as session:
            # 1. Основной источник: WhatToMine JSON API
            wtm_data = await make_request(session, settings.whattomine_asics_url)
            if wtm_data and isinstance(wtm_data, dict) and "asics" in wtm_data:
                miners = self._parse_whattomine_data(wtm_data["asics"])
                logger.info(f"Получено {len(miners)} майнеров с WhatToMine.")

        # 2. Если основной источник не сработал, используем резервный список из файла
        if not miners:
            logger.warning("WhatToMine не ответил, используем резервный список из файла.")
            miners = await self._get_fallback_asics()

        if not miners:
            logger.error("Все источники данных для ASIC недоступны.")
            return []

        # Сортируем майнеры по прибыльности в долларах (от большей к меньшей)
        sorted_miners = sorted(miners, key=lambda x: x.profitability, reverse=True)
        return sorted_miners

    def _parse_whattomine_data(self, asics_data: dict) -> List[AsicMiner]:
        """Парсит данные, полученные от WhatToMine JSON API."""
        parsed_miners = []
        for key, data in asics_data.items():
            try:
                # Пропускаем майнеры, у которых нет данных о прибыльности
                if data.get("profitability") is None:
                    continue

                miner = AsicMiner(
                    name=data.get("name", "Unknown Miner"),
                    profitability=float(data.get("profitability", 0)),
                    algorithm=data.get("algorithm", "Unknown"),
                    power=int(data.get("power", 0)),
                )
                parsed_miners.append(miner)
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Не удалось распарсить запись для майнера {key}: {e}")
        return parsed_miners

    async def _get_fallback_asics(self) -> List[AsicMiner]:
        """
        Загружает резервный список ASIC-майнеров из JSON-файла.
        """
        try:
            with open(settings.fallback_asics_path, 'r', encoding='utf-8') as f:
                fallback_data = json.load(f)

            miners = [AsicMiner(**item) for item in fallback_data]
            logger.info(f"Успешно загружено {len(miners)} майнеров из резервного файла.")
            return miners
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Не удалось загрузить или распарсить резервный файл {settings.fallback_asics_path}: {e}")
            return []

    async def get_asic_by_name(self, name: str) -> Optional[AsicMiner]:
        """
        Находит ASIC-майнер по его имени.
        """
        all_asics = await self.get_profitable_asics()
        for asic in all_asics:
            if asic.name == name:
                return asic
        return None