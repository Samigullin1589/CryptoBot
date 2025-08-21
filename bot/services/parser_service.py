# bot/services/parser_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Отказоустойчивый сервис для парсинга данных с внешних
# источников с улучшенной логикой обхода защиты и валидацией данных.

import asyncio
from typing import Any, Dict, List, Optional

import backoff
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import ValidationError

from bot.config.settings import settings
from bot.utils.http_client import http_session
from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name, parse_power

# Исключения, при которых оправданы повторные попытки запроса
RETRYABLE_EXCEPTIONS = (
    httpx.RequestError,
    httpx.HTTPStatusError,
    TimeoutError,
    asyncio.TimeoutError,
)

def _log_giveup(details):
    """Логирует финальную ошибку после всех попыток backoff."""
    logger.error(
        f"Запрос не удался после {details['tries']} попыток. "
        f"Ошибка: {details.get('exception')}"
    )

class ParserService:
    """
    Специализированный сервис для парсинга данных с внешних веб-сайтов и API.
    Оснащен механизмами повторных запросов и имитацией браузера.
    """

    def __init__(self):
        """Инициализирует сервис с конфигурацией эндпоинтов."""
        self.config = settings.ENDPOINTS
        logger.info("Сервис ParserService инициализирован.")

    @staticmethod
    def _extract_vendor_from_name(name: str) -> str:
        """
        Извлекает название производителя (вендора) из полного наименования ASIC.
        Использует список известных производителей для повышения точности.
        """
        name_lower = name.lower()
        vendors = [
            "antminer", "whatsminer", "jasminer", "goldshell", "canaan", 
            "innosilicon", "bombax", "elphapex", " Canaan", "Bitmain"
        ]
        for vendor in vendors:
            if vendor.lower() in name_lower:
                # Возвращаем стандартизированное название
                if vendor.lower() in ["bitmain", "antminer"]:
                    return "Antminer"
                return vendor.capitalize()
        return "Unknown"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, on_giveup=_log_giveup)
    async def _fetch(self, url: str, response_type: str = 'json') -> Optional[Any]:
        """
        Выполняет HTTP-запрос с логикой повторных попыток и заголовками,
        имитирующими браузер для обхода базовых защит от парсинга.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Connection': 'keep-alive',
        }
        async with http_session() as client:
            response = await client.get(url, headers=headers, timeout=20, follow_redirects=True)
            response.raise_for_status()
            if response_type == 'json':
                return response.json()
            return response.text()

    async def fetch_from_whattomine(self) -> List[AsicMiner]:
        """Получает и парсит данные с API WhatToMine."""
        if not self.config.WHATTOOMINE_API:
            return []
        
        logger.info("Парсер: Запрашиваю данные с WhatToMine API...")
        try:
            data = await self._fetch(self.config.WHATTOOMINE_API)
            if not data or "asics" not in data:
                logger.warning("Парсер: Не получены валидные данные от WhatToMine.")
                return []

            asics = []
            for asic_id, details in data["asics"].items():
                try:
                    # Добавляем вендора и валидируем через Pydantic
                    details['vendor'] = self._extract_vendor_from_name(details.get('name', ''))
                    asics.append(AsicMiner(id=asic_id, **details))
                except ValidationError as e:
                    logger.warning(f"Ошибка валидации ASIC с WhatToMine (ID: {asic_id}): {e}")
            
            logger.info(f"Парсер: Успешно получено и валидировано {len(asics)} ASIC с WhatToMine.")
            return asics
        except Exception as e:
            logger.exception(f"Парсер: Критическая ошибка при работе с WhatToMine: {e}")
            return []

    async def fetch_from_asicminervalue(self) -> List[AsicMiner]:
        """Получает и парсит данные со страницы AsicMinerValue."""
        if not self.config.ASICMINERVALUE_URL:
            return []
            
        logger.info("Парсер: Запрашиваю данные с AsicMinerValue...")
        try:
            html_content = await self._fetch(self.config.ASICMINERVALUE_URL, response_type='text')
            if not html_content:
                return []

            soup = BeautifulSoup(html_content, 'lxml')
            table_body = soup.find('table', class_='table-hover').find('tbody')
            if not table_body:
                logger.warning("Парсер: Не найдена таблица для парсинга на AsicMinerValue.")
                return []

            asics = []
            for row in table_body.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 5 or not (name_tag := cols[1].find('a')):
                        continue
                    
                    name = name_tag.text.strip()
                    profit_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    
                    asics.append(AsicMiner(
                        id=normalize_asic_name(name),
                        name=name,
                        vendor=self._extract_vendor_from_name(name),
                        profitability=float(profit_text) if profit_text != 'N/A' else 0.0,
                        power=parse_power(cols[4].text.strip()) or 0,
                        hashrate=cols[2].text.strip(),
                        algorithm="Unknown"  # AsicMinerValue не предоставляет алгоритм в таблице
                    ))
                except (AttributeError, ValueError, IndexError, TypeError, ValidationError) as e:
                    logger.debug(f"Не удалось распарсить строку ASIC: {row}. Ошибка: {e}")
                    continue
            
            logger.info(f"Парсер: Успешно получено и валидировано {len(asics)} ASIC с AsicMinerValue.")
            return asics
        except Exception as e:
            logger.exception(f"Парсер: Критическая ошибка при работе с AsicMinerValue: {e}")
            return []

    async def fetch_minerstat_hardware_specs(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Получает полный справочник спецификаций оборудования с MinerStat."""
        if not self.config.MINERSTAT_API:
            return None
        
        logger.info("Парсер: Запрашиваю справочник спецификаций с MinerStat API...")
        try:
            hardware_data = await self._fetch(f"{self.config.MINERSTAT_API}/hardware")
            if not isinstance(hardware_data, list):
                return None
            
            specs_db = {
                normalize_asic_name(hw['name']): {
                    "power": hw.get('power_consumption'), 
                    "algorithm": hw.get('algorithm')
                }
                for hw in hardware_data if 'name' in hw and hw.get('type') == 'ASIC'
            }
            logger.info(f"Загружен справочник из {len(specs_db)} ASIC с MinerStat.")
            return specs_db
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с MinerStat hardware API: {e}")
            return None