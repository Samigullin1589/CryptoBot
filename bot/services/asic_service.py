import asyncio
import logging
from typing import List, Dict

import aiohttp
from bs4 import BeautifulSoup
from cachetools import TTLCache
from fuzzywuzzy import process, fuzz

from bot.utils.async_cache_local import cached 
from bot.config.settings import settings
from bot.utils.models import AsicMiner
from bot.utils.helpers import make_request, parse_power, parse_profitability

logger = logging.getLogger(__name__)

class AsicService:
    cache = TTLCache(maxsize=1, ttl=settings.asic_cache_update_hours * 3600)

    @cached(cache)
    async def get_profitable_asics(self) -> List[AsicMiner]:
        logger.info("Updating ASIC miners cache...")
        async with aiohttp.ClientSession() as session:
            tasks = [self._scrape_asicminervalue(session), self._fetch_whattomine_asics(session)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_miners = []
        for res in results:
            if isinstance(res, list):
                all_miners.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Error fetching ASIC data source: {res}")

        if not all_miners:
            logger.warning("Using fallback ASIC list because all sources failed.")
            return [AsicMiner(**asic) for asic in settings.fallback_asics]

        final_miners: Dict[str, AsicMiner] = {}
        for miner in sorted(all_miners, key=lambda m: m.name):
            best_match, score = process.extractOne(miner.name, final_miners.keys(), scorer=fuzz.token_set_ratio) if final_miners else (None, 0)
            
            if score > 90 and best_match:
                existing = final_miners[best_match]
                if miner.profitability > existing.profitability:
                    existing.profitability = miner.profitability
                existing.algorithm = existing.algorithm or miner.algorithm
                existing.hashrate = existing.hashrate or miner.hashrate
                existing.power = existing.power or miner.power
            else:
                final_miners[miner.name] = miner
        
        sorted_list = sorted(final_miners.values(), key=lambda m: m.profitability, reverse=True)
        logger.info(f"ASIC cache updated with {len(sorted_list)} unique devices.")
        return sorted_list

    async def find_asics_by_algorithm(self, algorithm: str) -> List[AsicMiner]:
        if not algorithm:
            return []
            
        all_asics = await self.get_profitable_asics()
        normalized_algo = algorithm.lower().replace('-', '').replace('_', '')
        
        relevant_asics = [
            asic for asic in all_asics 
            if asic.algorithm and normalized_algo in asic.algorithm.lower().replace('-', '').replace('_', '')
        ]
        
        return sorted(relevant_asics, key=lambda x: x.profitability, reverse=True)

    async def _scrape_asicminervalue(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        miners = []
        html = await make_request(session, settings.asicminervalue_url, 'text')
        if not html: return miners
        
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table', {'id': 'datatable'})
        if not table or not table.tbody: return miners
        
        for row in table.tbody.find_all('tr', limit=50):
            cols = row.find_all('td')
            if len(cols) > 4:
                try:
                    name = cols[1].find('a').text.strip()
                    profitability = parse_profitability(cols[3].text)
                    power = parse_power(cols[4].text)
                    if profitability > 0:
                        miners.append(AsicMiner(name=name, profitability=profitability, power=power, source='AsicMinerValue'))
                except (AttributeError, ValueError) as e:
                    logger.warning(f"Failed to parse row on AsicMinerValue", extra={'error': str(e)})
                    continue
        logger.info(f"Scraped {len(miners)} miners from AsicMinerValue")
        return miners

    async def _fetch_whattomine_asics(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        miners = []
        # ИСПРАВЛЕНИЕ: Добавляем User-Agent, чтобы избежать ошибки 406
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        data = await make_request(session, settings.whattomine_asics_url, headers=headers)
        if not data or 'asics' not in data:
            if data is not None:
                logger.warning(f"WhatToMine API returned unexpected data: {str(data)[:200]}")
            return miners
        
        for name, asic_data in data['asics'].items():
            if asic_data.get('status') == 'Active' and 'revenue' in asic_data:
                try:
                    profit = parse_profitability(asic_data['revenue'])
                    if profit > 0:
                        miners.append(AsicMiner(
                            name=name, profitability=profit, algorithm=asic_data.get('algorithm'),
                            hashrate=str(asic_data.get('hashrate')), power=parse_power(str(asic_data.get('power', 0))),
                            source='WhatToMine'
                        ))
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse ASIC data from WhatToMine for '{name}'")
        logger.info(f"Fetched {len(miners)} miners from WhatToMine")
        return miners