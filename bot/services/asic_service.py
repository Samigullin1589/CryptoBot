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
        Главный, усиленный метод, который запускается по расписанию.
        Он последовательно пытается получить данные из нескольких источников.
        """
        logger.info("="*20)
        logger.info("STARTING SCHEDULED ASIC DB UPDATE")
        logger.info("="*20)
        
        final_asics = []
        
        async with aiohttp.ClientSession() as session:
            # --- Попытка 1: WhatToMine API (основной источник) ---
            logger.info("[Step 1/3] Trying primary source: WhatToMine API...")
            final_asics = await self._fetch_from_whattomine_api(session)
            
            # --- Попытка 2: AsicMinerValue Parser (вторичный источник) ---
            if not final_asics:
                logger.warning("[Step 1/3] FAILED. WhatToMine API returned no valid data.")
                logger.info("[Step 2/3] Trying secondary source: AsicMinerValue Parser...")
                final_asics = await self._fetch_from_asicminervalue(session)
            
            # --- Попытка 3: Локальный JSON (аварийный источник) ---
            if not final_asics:
                logger.warning("[Step 2/3] FAILED. AsicMinerValue Parser returned no valid data.")
                logger.info("[Step 3/3] Trying final source: Local fallback_asics.json...")
                
                if settings.fallback_asics and isinstance(settings.fallback_asics, list):
                    logger.info(f"Loaded {len(settings.fallback_asics)} ASICs from fallback JSON.")
                    final_asics = [AsicMiner(**asic_data) for asic_data in settings.fallback_asics]
                else:
                    logger.error("Local fallback_asics.json is empty or invalid.")
                    final_asics = []

        # --- Финальная проверка и кэширование ---
        if not final_asics:
            logger.error("CRITICAL: All data sources failed completely. Cache will not be updated.")
            return []

        # Фильтруем любые потенциально невалидные записи (без имени или доходности)
        valid_asics = [asic for asic in final_asics if asic.name and asic.profitability is not None]
        
        if not valid_asics:
            logger.error("All sources failed to provide any valid ASIC entries. Cache will not be updated.")
            return []

        logger.info(f"Update successful. Total valid ASICs found: {len(valid_asics)}. Caching to Redis.")
        await self._cache_asics_to_redis(valid_asics)
        await self.redis.set(self.LAST_UPDATE_KEY, datetime.now(timezone.utc).isoformat())
        return sorted(valid_asics, key=lambda x: x.profitability, reverse=True)


    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        """Сохраняет список ASIC'ов в Redis в виде хэшей, предварительно очистив старые данные."""
        logger.info(f"Preparing to cache {len(asics)} ASICs to Redis...")
        async with self.redis.pipeline() as pipe:
            old_keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if old_keys:
                logger.info(f"Deleting {len(old_keys)} old ASIC keys from Redis.")
                await pipe.delete(*old_keys)

            cached_count = 0
            for asic in asics:
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
        try:
            data = await make_request(session, settings.whattomine_asics_url)
            if not data or "asics" not in data:
                logger.warning("WTM fetch failed: Invalid data structure or empty response.")
                return None
            
            asics = []
            for key, asic_data in data["asics"].items():
                try:
                    if "revenue" not in asic_data: continue
                    profitability_str = asic_data.get("revenue", "0").replace("$", "").strip()
                    asics.append(AsicMiner(
                        name=key,
                        profitability=float(profitability_str),
                        algorithm=asic_data.get("algorithm"),
                        power=parse_power(str(asic_data.get("power", 0))),
                        hashrate=asic_data.get("hashrate"),
                        efficiency=None
                    ))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse WTM ASIC data for key '{key}': {e}. Skipping.")
                    continue
            
            if not asics:
                logger.warning("WTM parsing resulted in an empty list, though API responded.")
                return None

            logger.info(f"Successfully fetched {len(asics)} ASICs from WhatToMine.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during WhatToMine fetch: {e}")
            return None

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Парсит данные с сайта asicminervalue.com. Менее надежный источник."""
        try:
            html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
            if not html_content:
                logger.warning("AMV fetch failed: Could not download HTML.")
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table', {'id': 'datatable'})
            if not table or not table.find('tbody'):
                logger.warning("AMV parsing failed: Could not find data table. Site structure may have changed.")
                return None

            asics = []
            for row in table.tbody.find_all('tr'):
                try:
                    cols = row.find_all('td')
                    if len(cols) < 6: continue
                    name = cols[1].find('a').text.strip()
                    profitability_text = cols[3].text.strip().replace('$', '').replace('/day', '').strip()
                    power_text = cols[4].text.strip().replace('W', '').strip()
                    if not name or not profitability_text or not power_text: continue
                    
                    asics.append(AsicMiner(
                        name=name,
                        profitability=float(profitability_text),
                        power=int(power_text),
                        hashrate=cols[2].text.strip(),
                        efficiency=cols[5].text.strip(),
                        algorithm="Unknown"
                    ))
                except (AttributeError, ValueError, IndexError, TypeError) as e:
                    logger.warning(f"Could not parse a row on AMV: {e}. Skipping row.")
                    continue
            
            if not asics:
                logger.warning("AMV parsing resulted in an empty list, though table was found.")
                return None

            logger.info(f"Successfully fetched {len(asics)} ASICs from AsicMinerValue.")
            return asics
        except Exception as e:
            logger.error(f"An unexpected error occurred during AsicMinerValue fetch: {e}")
            return None
    
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
        if power <= 0 or electricity_cost < 0: return profitability
        power_kwh_per_day = (power / 1000) * 24
        daily_cost = power_kwh_per_day * electricity_cost
        return profitability - daily_cost

    async def get_top_asics(self, count: int = 10, electricity_cost: float = 0.0) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """Достает все ASIC из кэша Redis, рассчитывает чистую прибыль и возвращает топ."""
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        
        if not keys:
            logger.info("ASIC cache is empty. Forcing database update.")
            await self.update_asics_db()
            keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if not keys:
                logger.error("Failed to populate cache even after forced update.")
                return [], await self.get_last_update_time()

        pipe = self.redis.pipeline()
        for key in keys: pipe.hgetall(key)
        results = await pipe.execute()
        
        asics = []
        for data in results:
            if not data: continue
            try:
                profitability = float(data.get(b'profitability', b'0.0'))
                power = int(data.get(b'power', b'0'))
                net_profit = self.calculate_net_profit(profitability, power, electricity_cost)
                asics.append(AsicMiner(
                    name=data.get(b'name', b'Unknown').decode('utf-8'),
                    profitability=net_profit,
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
        if not normalized_query: return None
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        for key_bytes in keys:
            key_str = key_bytes.decode('utf-8')
            if normalized_query in key_str.replace('asic_passport:', ''):
                raw_data = await self.redis.hgetall(key_bytes)
                return {k.decode('utf-8'): v.decode('utf-8') for k, v in raw_data.items()}
        return None
