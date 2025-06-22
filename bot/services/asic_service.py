import asyncio
import logging
from typing import List, Dict
import aiohttp
from async_lru import alru_cache
from bs4 import BeautifulSoup
from fuzzywuzzy import process, fuzz
from playwright.async_api import async_playwright

from bot.config.settings import settings
from bot.utils.models import AsicMiner
from bot.utils.helpers import make_request, parse_power, parse_profitability

logger = logging.getLogger(__name__)

def _process_and_merge_miners(all_miners_raw: List[AsicMiner]) -> List[AsicMiner]:
    if not all_miners_raw:
        return []
    final_miners: Dict[str, AsicMiner] = {}
    for miner in sorted(all_miners_raw, key=lambda m: m.name):
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
    return sorted(final_miners.values(), key=lambda m: m.profitability, reverse=True)

class AsicService:
    @alru_cache(maxsize=1, ttl=settings.asic_cache_update_hours * 3600)
    async def get_profitable_asics(self) -> List[AsicMiner]:
        logger.info("Updating ASIC miners cache...")
        
        tasks = [
            self._fetch_whattomine_asics_playwright(),
            self._scrape_asicminervalue()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_miners = []
        for res in results:
            if isinstance(res, list) and res:
                all_miners.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"A data source failed: {res}")

        if not all_miners:
            logger.warning("All data sources failed. Using reliable fallback ASIC list.")
            return [AsicMiner(**asic) for asic in settings.fallback_asics]

        loop = asyncio.get_running_loop()
        processed_list = await loop.run_in_executor(None, _process_and_merge_miners, all_miners)
          
        logger.info(f"ASIC cache updated with {len(processed_list)} unique devices.")
        return processed_list

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

    async def _scrape_asicminervalue(self) -> List[AsicMiner]:
        miners = []
        logger.info("Fetching data from AsicMinerValue...")
        async with aiohttp.ClientSession() as session:
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
        logger.info(f"Scraped {len(miners)} miners from AsicMinerValue.")
        return miners

    async def _fetch_whattomine_asics_playwright(self) -> List[AsicMiner]:
        logger.info("Fetching WhatToMine data using Playwright...")
        miners = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(settings.whattomine_asics_url, timeout=60000)
                
                json_response = await page.evaluate("() => fetch(window.location.href).then(res => res.json())")
                await browser.close()

            if not json_response or 'asics' not in json_response:
                logger.warning(f"WhatToMine (Playwright) returned unexpected data.")
                return miners

            for name, asic_data in json_response['asics'].items():
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
            logger.info(f"Successfully fetched {len(miners)} miners from WhatToMine using Playwright.")
            return miners
        except Exception as e:
            logger.error(f"Critical error fetching from WhatToMine using Playwright: {e}")
            return []