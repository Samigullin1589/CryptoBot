# ===============================================================
# Файл: bot/services/parser_service.py (НОВЫЙ ФАЙЛ)
# Описание: Специализированный сервис, отвечающий за парсинг
# данных об ASIC-майнерах с различных внешних источников.
# Выделен из AsicService для соответствия принципу единой
# ответственности.
# ===============================================================

import logging
from typing import List

import aiohttp
from bs4 import BeautifulSoup

from bot.config.settings import settings
from bot.utils.helpers import make_request, parse_power
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class ParserService:
    """
    Отвечает за извлечение данных об ASIC из внешних веб-источников и API.
    """
    def __init__(self, http_session: aiohttp.ClientSession):
        self.session = http_session

    async def fetch_whattomine_data(self) -> List[AsicMiner]:
        """Получает и парсит данные из API WhatToMine."""
        logger.info("Fetching data from WhatToMine API...")
        try:
            data = await make_request(self.session, settings.api_endpoints.whattomine_asics_url)
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

    async def fetch_asicminervalue_data(self) -> List[AsicMiner]:
        """Получает и парсит данные, скрейпя сайт AsicMinerValue."""
        logger.info("Fetching data from AsicMinerValue...")
        try:
            html_content = await make_request(self.session, settings.api_endpoints.asicminervalue_url, response_type='text')
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

