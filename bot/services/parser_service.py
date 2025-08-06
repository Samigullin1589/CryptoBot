# ===============================================================
# Файл: bot/services/parser_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Отказоустойчивый сервис для парсинга данных с внешних
# источников с встроенной логикой повторных запросов.
# ИСПРАВЛЕНИЕ: Добавлен недостающий импорт 'asyncio'.
# ===============================================================
import logging
import asyncio # <--- ИСПРАВЛЕНО: Добавлен недостающий импорт
from typing import List, Dict, Any, Optional

import aiohttp
import backoff
from bs4 import BeautifulSoup

from bot.config.settings import EndpointsConfig
from bot.utils.models import AsicMiner
from bot.utils.text_utils import parse_power, normalize_asic_name

logger = logging.getLogger(__name__)

# Определяем ошибки, при которых стоит повторять запрос
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

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, on_giveup=lambda details: logger.error(
        f"HTTP request failed after {details['tries']} tries. Giving up. Error: {details.get('exception')}"
    ))
    async def _fetch(self, url: str, response_type: str = 'json') -> Optional[Any]:
        """Выполняет HTTP-запрос с логикой повторных попыток."""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        async with self.session.get(url, headers=headers, timeout=15) as response:
            response.raise_for_status()
            if response_type == 'json':
                return await response.json()
            return await response.text()

    async def fetch_from_whattomine(self) -> List[AsicMiner]:
        """Получает и парсит данные с API WhatToMine."""
        if not self.config.whattomine_api:
            logger.warning("URL для WhatToMine не задан в конфигурации. Пропуск.")
            return []
        
        logger.info("Парсер: Запрашиваю данные с WhatToMine API...")
        try:
            data = await self._fetch(str(self.config.whattomine_api))
            if not data or "asics" not in data:
                logger.warning("Парсер: Не получены валидные данные от WhatToMine.")
                return []

            asics = []
            for asic_id, details in data["asics"].items():
                try:
                    asics.append(AsicMiner(
                        id=asic_id,
                        name=details.get("name", asic_id),
                        profitability=float(details.get("profitability", 0)),
                        algorithm=details.get("algorithm"),
                        power=parse_power(str(details.get("power", 0))),
                        hashrate=str(details.get("hashrate", "N/A"))
                    ))
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Парсер: Ошибка обработки записи WhatToMine '{asic_id}': {e}. Пропускаю.")
                    continue
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с WhatToMine: {e}", exc_info=True)
            return []

    async def fetch_from_asicminervalue(self) -> List[AsicMiner]:
        """Получает и парсит данные со страницы AsicMinerValue."""
        if not self.config.asicminervalue_url:
            logger.warning("URL для AsicMinerValue не задан в конфигурации. Пропуск.")
            return []
            
        logger.info("Парсер: Запрашиваю данные с AsicMinerValue...")
        try:
            html_content = await self._fetch(str(self.config.asicminervalue_url), response_type='text')
            if not html_content: return []

            soup = BeautifulSoup(html_content, 'lxml')
            table_body = soup.select_one('table#miners tbody')
            if not table_body:
                logger.warning("Парсер: Не найдена таблица #miners в HTML от AsicMinerValue.")
                return []

            asics = []
            for row in table_body.find_all('tr', attrs={'data-name': True}):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 6: continue
                    
                    name_tag = cols[1].find('a')
                    if not name_tag: continue
                    
                    name = name_tag.text.strip()
                    profit_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip()
                    
                    asics.append(AsicMiner(
                        id=normalize_asic_name(name),
                        name=name,
                        profitability=float(profit_text),
                        power=parse_power(power_text),
                        hashrate=cols[2].text.strip(),
                        algorithm="Unknown"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Парсер: Ошибка обработки строки AsicMinerValue: {e}. Пропускаю.")
                    continue
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с AsicMinerValue: {e}", exc_info=True)
            return []

    async def fetch_minerstat_hardware_specs(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Получает полный справочник спецификаций оборудования с MinerStat."""
        if not self.config.minerstat_api:
            logger.warning("URL для MinerStat не задан в конфигурации. Пропуск.")
            return None
            
        logger.info("Парсер: Запрашиваю справочник спецификаций с MinerStat API...")
        try:
            hardware_data = await self._fetch(f"{self.config.minerstat_api}/hardware")
            if not hardware_data or not isinstance(hardware_data, list):
                logger.error("Парсер: Не удалось получить или неверный формат от MinerStat hardware API.")
                return None
            
            return {
                normalize_asic_name(hw['name']): {"power": hw.get('power_consumption'), "algorithm": hw.get('algorithm')}
                for hw in hardware_data if 'name' in hw and hw.get('type') == 'ASIC'
            }
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с MinerStat hardware API: {e}", exc_info=True)
            return None
