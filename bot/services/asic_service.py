import asyncio
import logging
from typing import List, Optional

import aiohttp
from async_lru import alru_cache
from bs4 import BeautifulSoup

from bot.config.settings import settings
from bot.utils.helpers import make_request, parse_power, parse_profitability
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class AsicService:
    @alru_cache(maxsize=1, ttl=3600 * settings.asic_cache_update_hours)
    async def get_profitable_asics(self) -> List[AsicMiner]:
        """Получает список ASIC-майнеров, используя несколько источников с откатом."""
        logger.info("Updating ASIC miners cache...")
        
        async with aiohttp.ClientSession() as session:
            # 1. Основной метод: прямой API-запрос к WhatToMine
            asics = await self._fetch_from_whattomine_api(session)
            if asics:
                logger.info(f"Successfully fetched {len(asics)} ASICs from WhatToMine API.")
                return sorted(asics, key=lambda x: x.profitability, reverse=True)

            # 2. Резервный метод: парсинг AsicMinerValue
            logger.warning("WhatToMine API failed, falling back to AsicMinerValue.")
            asics = await self._fetch_from_asicminervalue(session)
            if asics:
                logger.info(f"Successfully fetched {len(asics)} ASICs from AsicMinerValue.")
                return sorted(asics, key=lambda x: x.profitability, reverse=True)

        # 3. Крайний резервный метод: использование статического списка
        logger.warning("All external data sources failed. Using reliable fallback ASIC list.")
        return sorted([AsicMiner(**asic) for asic in settings.fallback_asics], key=lambda x: x.profitability, reverse=True)

    async def _fetch_from_whattomine_api(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Получает данные с JSON-эндпоинта WhatToMine."""
        data = await make_request(session, settings.whattomine_asics_url)
        if not data or "asics" not in data:
            return None
        
        asics = []
        for key, asic_data in data["asics"].items():
            try:
                profitability_str = asic_data.get("revenue", "0").replace("$", "")
                asics.append(AsicMiner(
                    name=key, # Используем ключ как имя
                    profitability=float(profitability_str),
                    algorithm=asic_data.get("algorithm", "Unknown"),
                    power=parse_power(str(asic_data.get("power", 0)))
                ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse WhatToMine ASIC data for key {key}: {e}")
                continue
        return asics

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Парсит данные с сайта asicminervalue.com."""
        html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, 'lxml')
        table = soup.find('table', {'id': 'datatable'})
        if not table or not table.find('tbody'):
            logger.warning("Could not find data table on AsicMinerValue.")
            return None

        asics = []
        for row in table.tbody.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            try:
                name = cols[1].find('a').text.strip()
                profitability_str = cols[3].text.strip().replace('$', '').replace('/day', '')
                power_str = cols[4].text.strip().replace('W', '')
                
                asics.append(AsicMiner(
                    name=name,
                    profitability=float(profitability_str),
                    power=int(power_str),
                    algorithm="Unknown" # На этой странице нет данных по алгоритму
                ))
            except (AttributeError, ValueError, IndexError, TypeError) as e:
                logger.warning(f"Could not parse row on AsicMinerValue: {e}")
                continue
        return asics

    async def find_asics_by_algorithm(self, algorithm: str) -> List[AsicMiner]:
        """Находит ASIC-майнеры по заданному алгоритму."""
        if not algorithm:
            return []
        all_asics = await self.get_profitable_asics()
        normalized_algo = algorithm.lower().replace('-', '').replace('_', '')
        relevant_asics = [
            asic for asic in all_asics 
            if asic.algorithm and normalized_algo in asic.algorithm.lower().replace('-', '').replace('_', '')
        ]
        return sorted(relevant_asics, key=lambda x: x.profitability, reverse=True)