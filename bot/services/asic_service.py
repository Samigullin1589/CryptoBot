import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import aiohttp
import redis.asyncio as redis
from async_lru import alru_cache
from bs4 import BeautifulSoup

from bot.config.settings import settings
from bot.utils.helpers import make_request, parse_power
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)

class AsicService:
    def __init__(self, redis_client: redis.Redis):
        """Сервис для работы с данными об ASIC-майнерах."""
        self.redis = redis_client
        self.LAST_UPDATE_KEY = "asics_last_update_utc"

    # --- БЛОК АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ БАЗЫ ДАННЫХ ---
    
    @alru_cache(maxsize=1, ttl=3600 * settings.asic_cache_update_hours)
    async def update_asics_db(self) -> List[AsicMiner]:
        """
        Главный метод, который запускается по расписанию.
        Он собирает данные со всех источников, кэширует их в Redis и возвращает список.
        """
        logger.info("Starting scheduled ASIC miners DB update...")
        
        async with aiohttp.ClientSession() as session:
            # Сначала пытаемся получить данные с основного, более надежного источника (API)
            asics = await self._fetch_from_whattomine_api(session)
            
            # Если первый источник не сработал, используем второй (парсер)
            if not asics:
                logger.warning("WhatToMine API failed or returned no data. Falling back to AsicMinerValue parser.")
                asics = await self._fetch_from_asicminervalue(session)
            
            # Если оба внешних источника не сработали, используем аварийный список
            if not asics:
                logger.error("All external data sources failed. Using reliable fallback ASIC list.")
                asics = [AsicMiner(**asic_data) for asic_data in settings.fallback_asics]

        # Кэшируем только если удалось получить хоть какие-то данные
        if asics:
            await self._cache_asics_to_redis(asics)
            logger.info(f"Successfully fetched and cached {len(asics)} ASICs.")
            # Сохраняем время успешного обновления
            await self.redis.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
        else:
            logger.error("Failed to fetch any ASIC data. Cache not updated.")

        # Всегда возвращаем отсортированный по доходности список
        return sorted(asics, key=lambda x: x.profitability, reverse=True)

    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        """Сохраняет список ASIC'ов в Redis в виде хэшей, предварительно очистив старые данные."""
        logger.info(f"Preparing to cache {len(asics)} ASICs to Redis...")
        async with self.redis.pipeline() as pipe:
            # Очищаем старые ключи
            old_keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if old_keys:
                logger.info(f"Deleting {len(old_keys)} old ASIC keys from Redis.")
                await pipe.delete(*old_keys)

            # Добавляем новые данные
            cached_count = 0
            for asic in asics:
                # Пропускаем асики без имени - это явный признак ошибки парсинга
                if not asic.name:
                    continue
                
                model_key = re.sub(r'[^a-z0-9]', '', asic.name.lower())
                redis_key = f"asic_passport:{model_key}"
                
                asic_dict = {
                    "name": asic.name,
                    "profitability": str(asic.profitability or 0.0),
                    "algorithm": asic.algorithm or "N/A",
                    "power": str(asic.power or 0),
                    "hashrate": asic.hashrate or "N/A",
                    "efficiency": asic.efficiency or "N/A"
                }
                pipe.hset(redis_key, mapping=asic_dict)
                cached_count += 1
            
            await pipe.execute()
        logger.info(f"Successfully cached {cached_count} ASICs.")

    async def _fetch_from_whattomine_api(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Получает данные с JSON-эндпоинта WhatToMine. Более надежный источник."""
        logger.info("Attempting to fetch data from WhatToMine API...")
        data = await make_request(session, settings.whattomine_asics_url)
        if not data or "asics" not in data:
            logger.warning("Failed to get valid data from WhatToMine API.")
            return None
        
        asics = []
        for key, asic_data in data["asics"].items():
            try:
                # Пропускаем, если нет данных о доходности
                if "revenue" not in asic_data:
                    continue

                profitability_str = asic_data.get("revenue", "0").replace("$", "").strip()
                
                asic = AsicMiner(
                    name=key,
                    profitability=float(profitability_str),
                    algorithm=asic_data.get("algorithm"),
                    power=parse_power(str(asic_data.get("power", 0))),
                    hashrate=asic_data.get("hashrate"),
                    efficiency=None # WTM не предоставляет этот параметр
                )
                asics.append(asic)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse WhatToMine ASIC data for key '{key}': {e}. Skipping.")
                continue
        logger.info(f"Fetched {len(asics)} ASICs from WhatToMine.")
        return asics

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Парсит данные с сайта asicminervalue.com. Менее надежный источник."""
        logger.info("Attempting to fetch data from AsicMinerValue by parsing HTML...")
        html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
        if not html_content:
            logger.warning("Failed to download HTML from AsicMinerValue.")
            return None
        
        soup = BeautifulSoup(html_content, 'lxml')
        table = soup.find('table', {'id': 'datatable'})
        if not table or not table.find('tbody'):
            logger.warning("Could not find data table on AsicMinerValue. The site structure may have changed.")
            return None

        asics = []
        for row in table.tbody.find_all('tr'):
            try:
                cols = row.find_all('td')
                if len(cols) < 6:
                    continue

                name = cols[1].find('a').text.strip()
                profitability_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                power_text = cols[4].text.strip().replace('W', '').strip()

                # Пропускаем строку, если ключевые данные отсутствуют
                if not name or not profitability_text or not power_text:
                    continue
                
                asic = AsicMiner(
                    name=name,
                    profitability=float(profitability_text),
                    power=int(power_text),
                    hashrate=cols[2].text.strip(),
                    efficiency=cols[5].text.strip(),
                    algorithm="Unknown" # AMV не указывает алгоритм в таблице
                )
                asics.append(asic)
            except (AttributeError, ValueError, IndexError, TypeError) as e:
                logger.warning(f"Could not parse a row on AsicMinerValue: {e}. Skipping row.")
                continue
        logger.info(f"Fetched {len(asics)} ASICs from AsicMinerValue.")
        return asics
    
    # --- БЛОК ПОЛУЧЕНИЯ ДАННЫХ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ---

    async def get_last_update_time(self) -> Optional[datetime]:
        """Возвращает время последнего обновления базы из Redis."""
        last_update_iso = await self.redis.get(self.LAST_UPDATE_KEY)
        if last_update_iso:
            return datetime.fromisoformat(last_update_iso.decode('utf-8'))
        return None

    @staticmethod
    def calculate_net_profit(profitability: float, power: int, electricity_cost: float) -> float:
        """Рассчитывает чистую прибыль с учетом стоимости электроэнергии."""
        if power <= 0 or electricity_cost < 0:
            return profitability
        
        power_kwh_per_day = (power / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        return profitability - daily_cost

    async def get_top_asics(self, count: int = 10, electricity_cost: float = 0.0) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """
        Достает все ASIC из кэша Redis, рассчитывает чистую прибыль и возвращает топ.
        Также возвращает время последнего обновления.
        """
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        
        # Если кэш пуст, принудительно обновляем базу
        if not keys:
            logger.info("ASIC cache is empty. Forcing database update.")
            await self.update_asics_db()
            keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if not keys:
                logger.error("Failed to populate cache even after forced update.")
                return [], await self.get_last_update_time()

        pipe = self.redis.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = await pipe.execute()
        
        asics = []
        for data in results:
            if not data:
                continue
            try:
                profitability = float(data.get(b'profitability', b'0.0'))
                power = int(data.get(b'power', b'0'))
                
                net_profit = self.calculate_net_profit(profitability, power, electricity_cost)

                asics.append(AsicMiner(
                    name=data.get(b'name', b'Unknown').decode('utf-8'),
                    profitability=net_profit, # Сохраняем чистую прибыль
                    power=power,
                    algorithm=data.get(b'algorithm', b'Unknown').decode('utf-8'),
                    hashrate=data.get(b'hashrate', b'N/A').decode('utf-8'),
                    efficiency=data.get(b'efficiency', b'N/A').decode('utf-8')
                ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not process cached ASIC data: {data}. Error: {e}")
                continue
        
        sorted_asics = sorted(asics, key=lambda x: x.profitability, reverse=True)
        last_update_time = await self.get_last_update_time()
        
        return sorted_asics[:count], last_update_time

    async def find_asic_by_query(self, model_query: str) -> Optional[dict]:
        """Ищет один ASIC в кэше Redis по нечеткому названию модели."""
        normalized_query = re.sub(r'[^a-z0-9]', '', model_query.lower())
        if not normalized_query:
            return None

        # redis.scan_iter возвращает байты, если на клиенте не задан decode_responses=True
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        
        for key_bytes in keys:
            key_str = key_bytes.decode('utf-8')
            if normalized_query in key_str.replace('asic_passport:', ''):
                # hgetall вернет словарь с байтовыми ключами и значениями
                raw_data = await self.redis.hgetall(key_bytes)
                # Декодируем для единообразия
                return {k.decode('utf-8'): v.decode('utf-8') for k, v in raw_data.items()}
        return None
