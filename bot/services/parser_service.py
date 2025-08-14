# ===============================================================
# Файл: bot/services/parser_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ УСИЛЕННАЯ)
# Описание: Отказоустойчивый сервис для парсинга данных с внешних
# источников с улучшенной логикой обхода защиты.
# ИСПРАВЛЕНИЕ: Добавлено извлечение производителя (vendor) из названия ASIC.
# ===============================================================
import logging
import asyncio
from typing import List, Dict, Any, Optional

import aiohttp
import backoff
from bs4 import BeautifulSoup

from bot.config.settings import EndpointsConfig
from bot.utils.models import AsicMiner
from bot.utils.text_utils import parse_power, normalize_asic_name

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientError,
    aiohttp.ClientResponseError,
    TimeoutError,
    asyncio.TimeoutError
)

class ParserService:
    """Специализированный сервис для парсинга данных с внешних источников."""
    
    def __init__(self, http_session: aiohttp.ClientSession, config: EndpointsConfig):
        self.session = http_session
        self.config = config

    @staticmethod
    def _extract_vendor_from_name(name: str) -> str:
        """Извлекает известного производителя из названия."""
        name_lower = name.lower()
        vendors = ["antminer", "whatsminer", "jasminer", "goldshell", "canaan", "innosilicon", "bombax", "elphapex"]
        for vendor in vendors:
            if vendor in name_lower:
                return vendor.capitalize()
        return "Unknown"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, on_giveup=lambda details: logger.error(
        f"HTTP request failed after {details['tries']} tries. Giving up. Error: {details.get('exception')}"
    ))
    async def _fetch(self, url: str, response_type: str = 'json') -> Optional[Any]:
        """Выполняет HTTP-запрос с логикой повторных попыток и полными заголовками."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        async with self.session.get(url, headers=headers, timeout=20, ssl=False) as response:
            response.raise_for_status()
            if response_type == 'json':
                return await response.json(content_type=None)
            return await response.text()

    async def fetch_from_whattomine(self) -> List[AsicMiner]:
        """Получает и парсит данные с API WhatToMine."""
        if not self.config.whattomine_api:
            return []
        
        logger.info("Парсер: Запрашиваю данные с WhatToMine API...")
        try:
            data = await self._fetch(str(self.config.whattomine_api))
            if not data or "asics" not in data:
                logger.warning("Парсер: Не получены валидные данные от WhatToMine.")
                return []

            asics = []
            for asic_id, details in data["asics"].items():
                details['vendor'] = self._extract_vendor_from_name(details.get('name', ''))
                asics.append(AsicMiner(id=asic_id, **details))

            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с WhatToMine: {e}", exc_info=True)
            return []

    async def fetch_from_asicminervalue(self) -> List[AsicMiner]:
        """Получает и парсит данные со страницы AsicMinerValue."""
        if not self.config.asicminervalue_url:
            return []
            
        logger.info("Парсер: Запрашиваю данные с AsicMinerValue...")
        try:
            html_content = await self._fetch(str(self.config.asicminervalue_url), response_type='text')
            if not html_content: return []

            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', class_='table-hover')
            if not table:
                logger.warning("Парсер: Не найдена таблица с классом 'table-hover' в HTML от AsicMinerValue.")
                return []
            
            table_body = table.find('tbody')
            if not table_body:
                return []

            asics = []
            for row in table_body.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 5: continue
                    
                    name_tag = cols[1].find('a')
                    if not name_tag: continue
                    
                    name = name_tag.text.strip()
                    profit_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip()
                    
                    asics.append(AsicMiner(
                        id=normalize_asic_name(name),
                        name=name,
                        vendor=self._extract_vendor_from_name(name),
                        profitability=float(profit_text) if profit_text != 'N/A' else 0.0,
                        power=parse_power(power_text) or 0,
                        hashrate=cols[2].text.strip(),
                        algorithm="Unknown"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError):
                    continue
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с AsicMinerValue: {e}", exc_info=True)
            return []

    async def fetch_minerstat_hardware_specs(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Получает полный справочник спецификаций оборудования с MinerStat."""
        if not self.config.minerstat_api:
            return None
        
        logger.info("Парсер: Запрашиваю справочник спецификаций с MinerStat API...")
        try:
            hardware_data = await self._fetch(f"{self.config.minerstat_api}/hardware")
            if not hardware_data or not isinstance(hardware_data, list):
                return None
            
            return {
                normalize_asic_name(hw['name']): {"power": hw.get('power_consumption'), "algorithm": hw.get('algorithm')}
                for hw in hardware_data if 'name' in hw and hw.get('type') == 'ASIC'
            }
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с MinerStat hardware API: {e}", exc_info=True)
            return None