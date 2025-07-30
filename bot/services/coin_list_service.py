# ===============================================================
# Файл: bot/services/coin_list_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Высокопроизводительный сервис для управления справочником
# криптовалют с использованием Redis-хеша в качестве поискового индекса.
# ===============================================================
import json
import logging
from typing import Optional, List, Dict, Any

import aiohttp
import backoff
import redis.asyncio as redis
from rapidfuzz import process, fuzz

from bot.config.settings import CoinListServiceConfig, EndpointsConfig
from bot.utils.keys import KeyFactory
from bot.utils.models import CoinInfo

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (aiohttp.ClientError, TimeoutError)

class CoinListService:
    """Сервис для управления справочником всех криптовалют."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        http_session: aiohttp.ClientSession,
        config: CoinListServiceConfig,
        endpoints: EndpointsConfig,
        ticker_aliases: Dict[str, str]
    ):
        self.redis = redis_client
        self.session = http_session
        self.config = config
        self.endpoints = endpoints
        self.ticker_aliases = ticker_aliases
        self.keys = KeyFactory

    @backoff.on_exception(backoff.expo, RETRYABLE_EXCEPTIONS, max_tries=3)
    async def _fetch(self, url: str) -> Optional[List[Dict]]:
        """Выполняет отказоустойчивый HTTP-запрос."""
        async with self.session.get(url, timeout=20) as response:
            response.raise_for_status()
            return await response.json()

    async def _fetch_from_coingecko(self) -> List[CoinInfo]:
        """Получает основной список монет с CoinGecko."""
        url = f"{self.endpoints.coingecko_api_base}/coins/list"
        data = await self._fetch(url)
        if not data or not isinstance(data, list):
            logger.warning("Не удалось получить список монет от CoinGecko.")
            return []
        
        coins = [
            CoinInfo(
                id=c.get('id'),
                symbol=c.get('symbol', '').lower(),
                name=c.get('name', 'Unknown')
            ) for c in data if c.get('id') and c.get('symbol')
        ]
        logger.info(f"Успешно получено {len(coins)} монет от CoinGecko.")
        return coins

    async def update_coin_list_cache(self):
        """Обновляет кэш и поисковый индекс монет."""
        logger.info("="*20 + " ЗАПУСК ОБНОВЛЕНИЯ СПИСКА МОНЕТ " + "="*20)
        
        coins = await self._fetch_from_coingecko()
        if not coins:
            logger.error("Основной источник (CoinGecko) недоступен. Обновление не удалось.")
            return

        # --- ГЕНИАЛЬНОЕ УЛУЧШЕНИЕ: Создаем поисковый индекс ---
        search_index = {}
        # 1. Добавляем ID, символы и имена
        for coin in coins:
            search_index[coin.id.lower()] = coin.id
            search_index[coin.symbol.lower()] = coin.id
            search_index[coin.name.lower()] = coin.id
        # 2. Добавляем кастомные псевдонимы из конфига
        for alias, symbol in self.ticker_aliases.items():
            # Находим ID для этого символа
            target_coin = next((c for c in coins if c.symbol.lower() == symbol.lower()), None)
            if target_coin:
                search_index[alias.lower()] = target_coin.id
        
        # Атомарно обновляем все в Redis
        async with self.redis.pipeline(transaction=True) as pipe:
            # Сначала удаляем старый индекс
            await pipe.delete(self.keys.coin_search_index_hash())
            # Сохраняем новый индекс
            await pipe.hset(self.keys.coin_search_index_hash(), mapping=search_index)
            # Сохраняем информацию о каждой монете в отдельном хэше
            for coin in coins:
                await pipe.hset(self.keys.coin_info_hash(coin.id), mapping=coin.model_dump())
            await pipe.execute()
            
        logger.info(f"Список из {len(coins)} монет и поисковый индекс из {len(search_index)} записей сохранены в Redis.")

    async def find_coin(self, query: str) -> Optional[CoinInfo]:
        """
        Мгновенно находит монету, используя поисковый индекс в Redis.
        """
        query = query.strip().lower()
        if not query:
            return None
            
        # --- ГЕНИАЛЬНОЕ УЛУЧШЕНИЕ: Один вызов к Redis для поиска ID ---
        coin_id = await self.redis.hget(self.keys.coin_search_index_hash(), query)
        
        if not coin_id:
            # Если точного совпадения нет, можно добавить опциональный нечеткий поиск по ключам индекса
            # Но для большинства случаев это будет избыточно и медленнее
            logger.warning(f"Монета по запросу '{query}' не найдена в индексе.")
            return None
        
        # --- Один вызов для получения данных о монете ---
        coin_data = await self.redis.hgetall(self.keys.coin_info_hash(coin_id))
        
        return CoinInfo.model_validate(coin_data) if coin_data else None