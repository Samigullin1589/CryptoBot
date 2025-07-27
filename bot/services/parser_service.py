# ===============================================================
# Файл: bot/services/parser_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Сервис, отвечающий исключительно за парсинг "сырых"
# данных об ASIC-майнерах с внешних веб-сайтов и API.
# ===============================================================
import logging
from typing import List

import aiohttp
from bs4 import BeautifulSoup

# --- ИСПРАВЛЕНИЕ: Импортируем утилиты из новых, правильных мест ---
from bot.utils.http_client import make_request
from bot.utils.text_utils import parse_power
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

from bot.utils.models import AsicMiner
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class ParserService:
    """
    Специализированный сервис для парсинга данных об ASIC с внешних источников.
    """
    def __init__(self, http_session: aiohttp.ClientSession):
        self.session = http_session
        self.config = settings.parser

    async def fetch_from_whattomine(self) -> List[AsicMiner]:
        """
        Получает и парсит данные об ASIC-майнерах с API WhatToMine.
        """
        logger.info("Парсер: Запрашиваю данные с WhatToMine API...")
        try:
            data = await make_request(self.session, self.config.whattomine_url)
            if not data or "coins" not in data:
                logger.warning("Парсер: Не получены валидные данные от WhatToMine.")
                return []

            asics = []
            for details in data["coins"].values():
                try:
                    if details.get("tag") and details.get("profitability") is not None:
                        asics.append(AsicMiner(
                            name=details["tag"],
                            profitability=float(details["profitability"]),
                            algorithm=details.get("algorithm"),
                            power=parse_power(str(details.get("power_consumption", 0))),
                            hashrate=str(details.get("hashrate", "N/A")),
                            source="WhatToMine"
                        ))
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Парсер: Ошибка обработки записи WhatToMine '{details.get('tag')}': {e}. Пропускаю.")
                    continue
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с WhatToMine: {e}", exc_info=True)
            return []

    async def fetch_from_asicminervalue(self) -> List[AsicMiner]:
        """
        Получает и парсит данные об ASIC-майнерах со страницы AsicMinerValue.
        """
        logger.info("Парсер: Запрашиваю данные с AsicMinerValue...")
        try:
            html_content = await make_request(self.session, self.config.asicminervalue_url, response_type='text')
            if not html_content:
                logger.warning("Парсер: Не получен HTML от AsicMinerValue. Пропускаю.")
                return []

            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', {'id': 'miners'})
            if not table or not table.find('tbody'):
                logger.warning("Парсер: Не найдена таблица в HTML от AsicMinerValue.")
                return []

            asics = []
            for row in table.tbody.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 6: continue

                    name_tag = cols[1].find('a')
                    if not name_tag: continue
                    
                    name = name_tag.text.strip()
                    profit_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip().replace('W', '').strip()

                    asics.append(AsicMiner(
                        name=name,
                        profitability=float(profit_text),
                        power=int(power_text),
                        hashrate=cols[2].text.strip(),
                        efficiency=cols[5].text.strip(),
                        algorithm="Unknown",
                        source="AsicMinerValue"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Парсер: Ошибка обработки строки AsicMinerValue: {e}. Пропускаю.")
                    continue
            logger.info(f"Парсер: Успешно получено {len(asics)} ASIC с AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"Парсер: Критическая ошибка при работе с AsicMinerValue: {e}", exc_info=True)
            return []
