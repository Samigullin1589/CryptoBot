# bot/services/parser_service.py
# Дата обновления: 23.08.2025
# Версия: 2.1.0
# Описание: Отказоустойчивый сервис для парсинга данных.

import asyncio
from typing import Any, Dict, List, Optional

import backoff
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import ValidationError

from bot.config.settings import settings
from bot.utils.http_client import HttpClient
from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name, parse_power

RETRYABLE_EXCEPTIONS = (httpx.RequestError, httpx.HTTPStatusError, TimeoutError, asyncio.TimeoutError)

def _log_giveup(details):
    logger.error(f"Запрос не удался после {details['tries']} попыток. Ошибка: {details.get('exception')}")

class ParserService:
    """
    Специализированный сервис для парсинга данных с внешних веб-сайтов и API.
    """
    def __init__(self, http_client: HttpClient):
        """Инициализирует сервис с зависимостями."""
        self.http_client = http_client
        self.config = settings.ENDPOINTS
        logger.info("Сервис ParserService инициализирован.")

    @staticmethod
    def _extract_vendor_from_name(name: str) -> str:
        name_lower = name.lower()
        vendors = ["antminer", "whatsminer", "jasminer", "goldshell", "canaan", "innosilicon", "bombax", "elphapex", "Bitmain"]
        for vendor in vendors:
            if vendor.lower() in name_lower:
                if vendor.lower() in ["bitmain", "antminer"]: return "Antminer"
                return vendor.capitalize()
        return "Unknown"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, on_giveup=_log_giveup)
    async def _fetch(self, url: str, response_type: str = 'json') -> Optional[Any]:
        return await self.http_client.get(url, response_type=response_type)

    async def fetch_from_whattomine(self) -> List[AsicMiner]:
        """Получает и парсит данные с API WhatToMine."""
        if not self.config.WHATTOOMINE_API: return []
        
        logger.info("Парсер: Запрашиваю данные с WhatToMine API...")
        try:
            data = await self._fetch(self.config.WHATTOOMINE_API)
            if not data or "asics" not in data: return []

            asics = []
            for asic_id, details in data["asics"].items():
                try:
                    details['vendor'] = self._extract_vendor_from_name(details.get('name', ''))
                    asics.append(AsicMiner(id=asic_id, **details))
                except ValidationError as e:
                    logger.warning(f"Ошибка валидации ASIC с WhatToMine (ID: {asic_id}): {e}")
            
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с WhatToMine.")
            return asics
        except Exception as e:
            logger.exception(f"Парсер: Критическая ошибка при работе с WhatToMine: {e}")
            return []

    async def fetch_from_asicminervalue(self) -> List[AsicMiner]:
        """Получает и парсит данные со страницы AsicMinerValue."""
        if not self.config.ASICMINERVALUE_URL: return []
            
        logger.info("Парсер: Запрашиваю данные с AsicMinerValue...")
        try:
            html_content = await self._fetch(self.config.ASICMINERVALUE_URL, response_type='text')
            if not html_content: return []

            soup = BeautifulSoup(html_content, 'lxml')
            table_body = soup.find('table', class_='table-hover').find('tbody')
            if not table_body: return []

            asics = []
            for row in table_body.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 5 or not (name_tag := cols[1].find('a')): continue
                    
                    name = name_tag.text.strip()
                    profit_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    
                    asics.append(AsicMiner(
                        id=normalize_asic_name(name), name=name,
                        vendor=self._extract_vendor_from_name(name),
                        profitability=float(profit_text) if profit_text != 'N/A' else 0.0,
                        power=parse_power(cols[4].text.strip()) or 0,
                        hashrate=cols[2].text.strip(), algorithm="Unknown"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError, ValidationError) as e:
                    logger.debug(f"Не удалось распарсить строку ASIC: {row}. Ошибка: {e}")
                    continue
            
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с AsicMinerValue.")
            return asics
        except Exception as e:
            logger.exception(f"Парсер: Критическая ошибка при работе с AsicMinerValue: {e}")
            return []

    async def fetch_minerstat_hardware_specs(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Получает справочник спецификаций оборудования с MinerStat."""
        if not self.config.MINERSTAT_API: return None
        
        logger.info("Парсер: Запрашиваю справочник спецификаций с MinerStat API...")
        try:
            hardware_data = await self._fetch(f"{self.config.MINERSTAT_API}/hardware")
            if not isinstance(hardware_data, list): return None
            
            specs_db = {
                normalize_asic_name(hw['name']): {"power": hw.get('power_consumption'), "algorithm": hw.get('algorithm')}
                for hw in hardware_data if 'name' in hw and hw.get('type') == 'ASIC'
            }
            logger.info(f"Загружен справочник из {len(specs_db)} ASIC с MinerStat.")
            return specs_db
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с MinerStat hardware API: {e}")
            return None