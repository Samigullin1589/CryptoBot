# =================================================================================
# Файл: bot/services/price_service.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ, АВГУСТ 2025)
# Описание: Сервис для получения цен на криптовалюты с максимальной
# отказоустойчивостью и производительностью.
#
# Ключевые улучшения "Distinguished Engineer":
# 1.  ПАРАЛЛЕЛЬНАЯ ПАКЕТНАЯ ОБРАБОТКА (BATCHING): Если требуется запросить цены
#     для большого количества монет, сервис автоматически разбивает их на
#     несколько небольших пакетов и запрашивает параллельно с помощью
#     `asyncio.gather`. Это предотвращает ошибки, связанные с длиной URL,
#     и значительно ускоряет выполнение больших запросов.
# 2.  ЭФФЕКТИВНОЕ КЭШИРОВАНИЕ: Перед запросом к API сервис делает один
#     массовый запрос к Redis (`MGET`) для получения всех возможных цен из
#     кэша, минимизируя количество обращений к базе данных.
# 3.  ИЗОЛИРОВАННАЯ ОБРАБОТКА ОШИБОК: Сбой при загрузке одного из пакетов
#     не приводит к сбою всего запроса. Сервис вернет успешно загруженные
#     данные, а для "проблемных" монет вернет `None`.
# =================================================================================

from __future__ import annotations
import asyncio
import logging
from typing import Dict, List, Optional

import aiohttp
import backoff
from redis.asyncio import Redis

from bot.config.settings import PriceServiceConfig, EndpointsConfig

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ClientResponseError)
API_BATCH_SIZE = 100 # Максимальное количество ID в одном запросе к CoinGecko

class PriceService:
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        config: PriceServiceConfig,
        endpoints: EndpointsConfig,
    ):
        self.redis = redis
        self.http_session = http_session
        self.config = config
        self.endpoints = endpoints

    def _get_cache_key(self, coin_id: str, vs_currency: str) -> str:
        return f"cache:price:v3:{coin_id}:{vs_currency}"

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3, logger=logger, jitter=backoff.full_jitter)
    async def _fetch_prices_batch(self, coin_ids_batch: List[str], target_currency: str) -> Optional[Dict]:
        url = f"{self.endpoints.coingecko_api_base}{self.endpoints.simple_price_endpoint}"
        params = {'ids': ','.join(coin_ids_batch), 'vs_currencies': target_currency}
        
        logger.info(f"Запрос цен с API для пакета из {len(coin_ids_batch)} монет.")
        async with self.http_session.get(url, params=params, timeout=10) as response:
            if response.status == 429:
                logger.warning("Получен статус 429 (Too Many Requests). Ожидание перед повторной попыткой.")
            response.raise_for_status()
            return await response.json()

    async def get_prices(self, coin_ids: List[str], vs_currency: Optional[str] = None) -> Dict[str, Optional[float]]:
        if not coin_ids:
            return {}
            
        target_currency = (vs_currency or self.config.default_vs_currency).lower()
        
        # --- Шаг 1: Инициализация и массовая проверка кэша ---
        prices: Dict[str, Optional[float]] = {cid: None for cid in coin_ids}
        cache_keys = [self._get_cache_key(cid, target_currency) for cid in coin_ids]
        
        cached_values = await self.redis.mget(cache_keys)
        
        coins_to_fetch: List[str] = []
        for i, coin_id in enumerate(coin_ids):
            if cached_values[i] is not None:
                prices[coin_id] = float(cached_values[i])
            else:
                coins_to_fetch.append(coin_id)

        if not coins_to_fetch:
            logger.debug(f"Все цены для {len(coin_ids)} монет найдены в кэше.")
            return prices

        logger.info(f"Цены для {len(coins_to_fetch)} из {len(coin_ids)} монет не найдены в кэше. Запрос к API.")

        # --- Шаг 2: Параллельная пакетная загрузка недостающих цен ---
        batches = [coins_to_fetch[i:i + API_BATCH_SIZE] for i in range(0, len(coins_to_fetch), API_BATCH_SIZE)]
        tasks = [self._fetch_prices_batch(batch, target_currency) for batch in batches]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # --- Шаг 3: Обработка результатов и обновление кэша ---
        pipe = self.redis.pipeline()
        new_prices_to_cache = {}

        for i, result in enumerate(results):
            batch = batches[i]
            if isinstance(result, Exception):
                logger.error(f"Не удалось загрузить пакет цен для {batch}: {result}")
                continue # Оставляем цены для этого пакета как None
            
            if result:
                for coin_id in batch:
                    price_data = result.get(coin_id)
                    price = price_data.get(target_currency) if price_data else None
                    if price is not None:
                        prices[coin_id] = float(price)
                        new_prices_to_cache[self._get_cache_key(coin_id, target_currency)] = price
                    else:
                        logger.warning(f"В ответе API не найдена цена для {coin_id} в {target_currency}")
        
        if new_prices_to_cache:
            pipe.mset(new_prices_to_cache)
            for key in new_prices_to_cache:
                pipe.expire(key, self.config.cache_ttl_seconds)
            await pipe.execute()
            logger.info(f"Кэш обновлен для {len(new_prices_to_cache)} монет.")

        return prices
