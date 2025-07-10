import asyncio
import logging
import re
from typing import List, Optional

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
        """Сервис теперь требует клиент Redis для кэширования."""
        self.redis = redis_client

    # --- БЛОК АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ БАЗЫ ДАННЫХ ---
    
    @alru_cache(maxsize=1, ttl=3600 * settings.asic_cache_update_hours)
    async def update_asics_db(self) -> List[AsicMiner]:
        """
        Главный метод, который запускается по расписанию.
        Он собирает данные со всех источников, кэширует их в Redis и возвращает список.
        """
        logger.info("Updating ASIC miners DB and caching to Redis...")
        
        async with aiohttp.ClientSession() as session:
            asics = await self._fetch_from_whattomine_api(session)
            if not asics:
                logger.warning("WhatToMine API failed, falling back to AsicMinerValue.")
                asics = await self._fetch_from_asicminervalue(session)
            
            if not asics:
                logger.warning("All external data sources failed. Using reliable fallback ASIC list.")
                asics = [AsicMiner(**asic) for asic in settings.fallback_asics]

        if asics:
            await self._cache_asics_to_redis(asics)
            logger.info(f"Successfully fetched and cached {len(asics)} ASICs.")
        
        return sorted(asics, key=lambda x: x.profitability, reverse=True)

    async def _cache_asics_to_redis(self, asics: List[AsicMiner]):
        """Сохраняет список ASIC'ов в Redis в виде хэшей."""
        logger.info(f"Caching {len(asics)} ASICs to Redis...")
        async with self.redis.pipeline() as pipe:
            # Сначала удалим старые записи, чтобы избавиться от неактуальных моделей
            old_keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
            if old_keys:
                await self.redis.delete(*old_keys)

            # Добавляем новые
            for asic in asics:
                # Создаем простой ключ для поиска
                model_key = re.sub(r'[^a-z0-9]', '', asic.name.lower())
                redis_key = f"asic_passport:{model_key}"
                
                asic_dict = {
                    "name": asic.name,
                    "profitability": str(asic.profitability),
                    "algorithm": asic.algorithm,
                    "power": str(asic.power or 0),
                    # Добавляем доп. поля для "паспорта"
                    "hashrate": asic.hashrate or "N/A",
                    "efficiency": asic.efficiency or "N/A"
                }
                pipe.hset(redis_key, mapping=asic_dict)
            await pipe.execute()
        logger.info("Successfully cached ASICs.")

    async def _fetch_from_whattomine_api(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Получает данные с JSON-эндпоинта WhatToMine."""
        data = await make_request(session, settings.whattomine_asics_url)
        if not data or "asics" not in data:
            return None
        
        asics = []
        for key, asic_data in data["asics"].items():
            try:
                profitability_str = asic_data.get("revenue", "0").replace("$", "")
                asics.append(AsicMiner(
                    name=key,
                    profitability=float(profitability_str),
                    algorithm=asic_data.get("algorithm", "Unknown"),
                    power=parse_power(str(asic_data.get("power", 0))),
                    hashrate=asic_data.get("hashrate", "N/A"),
                    efficiency=None # В этом API нет данных по эффективности
                ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse WhatToMine ASIC data for key {key}: {e}")
        return asics

    async def _fetch_from_asicminervalue(self, session: aiohttp.ClientSession) -> Optional[List[AsicMiner]]:
        """Парсит данные с сайта asicminervalue.com."""
        html_content = await make_request(session, settings.asicminervalue_url, response_type='text')
        if not html_content: return None
        
        soup = BeautifulSoup(html_content, 'lxml')
        table = soup.find('table', {'id': 'datatable'})
        if not table or not table.find('tbody'):
            logger.warning("Could not find data table on AsicMinerValue.")
            return None

        asics = []
        for row in table.tbody.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 6: continue
            try:
                asics.append(AsicMiner(
                    name=cols[1].find('a').text.strip(),
                    profitability=float(cols[3].text.strip().replace('$', '').replace('/day', '')),
                    power=int(cols[4].text.strip().replace('W', '')),
                    hashrate=cols[2].text.strip(),
                    efficiency=cols[5].text.strip(),
                    algorithm="Unknown"
                ))
            except (AttributeError, ValueError, IndexError, TypeError) as e:
                logger.warning(f"Could not parse row on AsicMinerValue: {e}")
        return asics
    
    # --- БЛОК ПОЛУЧЕНИЯ ДАННЫХ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ---

    async def get_all_cached_asics(self) -> List[AsicMiner]:
        """Достает все ASIC из кэша Redis и сортирует по доходности."""
        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        if not keys:
            # Если кэш пуст, принудительно обновляем его
            return await self.update_asics_db()
            
        pipe = self.redis.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = await pipe.execute()
        
        asics = [
            AsicMiner(
                name=data.get('name', 'Unknown'),
                profitability=float(data.get('profitability', 0.0)),
                power=int(data.get('power', 0)),
                algorithm=data.get('algorithm', 'Unknown'),
                hashrate=data.get('hashrate', 'N/A'),
                efficiency=data.get('efficiency', 'N/A')
            ) for data in results if data
        ]
        return sorted(asics, key=lambda x: x.profitability, reverse=True)


    async def find_asic_by_query(self, model_query: str) -> Optional[AsicMiner]:
        """Ищет один ASIC в кэше Redis по нечеткому названию модели."""
        normalized_query = re.sub(r'[^a-z0-9]', '', model_query.lower())
        if not normalized_query: return None

        keys = [key async for key in self.redis.scan_iter("asic_passport:*")]
        
        for key in keys:
            # Сравниваем нормализованный запрос с нормализованным ключом
            if normalized_query in key.decode('utf-8').replace('asicpassport', ''):
                data = await self.redis.hgetall(key)
                return AsicMiner(**{k:v for k,v in data.items()})
        return None