# ===============================================================
# Файл: bot/services/coin_list_service.py (ПРОДАКШН-ВЕРСЯ 2025)
# Описание: Сервис для управления справочником всех криптовалют.
# Отвечает за обновление, кэширование и поиск монет.
# ===============================================================
import json
import logging
from typing import Optional, List

import aiohttp
import redis.asyncio as redis
from rapidfuzz import process, fuzz

from bot.config.settings import settings
# --- ИСПРАВЛЕНИЕ: Импортируем утилиту из нового, правильного места ---
from bot.utils.http_client import make_request
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.models import CoinInfo

logger = logging.getLogger(__name__)

class CoinListService:
    """
    Сервис для управления справочником всех криптовалют.
    """
    def __init__(self, redis_client: redis.Redis, http_session: aiohttp.ClientSession):
        self.redis = redis_client
        self.session = http_session
        self.config = settings.coin_list_service

    async def _fetch_from_minerstat(self) -> List[CoinInfo]:
        """Получает полный список монет с MinerStat."""
        data = await make_request(self.session, self.config.minerstat_url)
        if not data or not isinstance(data, list):
            logger.warning("Не удалось получить список монет от MinerStat.")
            return []
        
        coins = [CoinInfo.model_validate(item) for item in data]
        logger.info(f"Успешно получено {len(coins)} монет от MinerStat.")
        return coins

    async def _fetch_from_coingecko(self) -> List[CoinInfo]:
        """Получает резервный список монет с CoinGecko."""
        data = await make_request(self.session, self.config.coingecko_url)
        if not data or not isinstance(data, list):
            logger.warning("Не удалось получить список монет от CoinGecko.")
            return []
            
        # Адаптируем данные от Gecko под нашу модель
        coins = [
            CoinInfo(
                coin=c.get('symbol', '').upper(), 
                name=c.get('name', 'Unknown'), 
                algorithm='Unknown'
            ) for c in data
        ]
        logger.info(f"Успешно получено {len(coins)} монет от CoinGecko.")
        return coins

    async def update_coin_list_cache(self) -> None:
        """
        Обновляет кэш списка монет, используя основной и резервный источники.
        """
        logger.info("="*20 + " ЗАПУСК ОБНОВЛЕНИЯ СПИСКА МОНЕТ " + "="*20)
        
        coins = await self._fetch_from_minerstat()
        if not coins:
            logger.warning("Основной источник (MinerStat) не ответил, использую резервный (CoinGecko).")
            coins = await self._fetch_from_coingecko()

        if not coins:
            logger.error("Все источники списка монет недоступны. Обновление не удалось.")
            return
            
        await self.redis.set(self.config.cache_key, json.dumps([c.model_dump() for c in coins]))
        logger.info(f"Список из {len(coins)} монет успешно сохранен в кэш Redis.")

    async def get_all_coins(self) -> List[CoinInfo]:
        """
        Получает полный список монет из кэша Redis.
        Если кэш пуст, запускает принудительное обновление.
        """
        cached_data = await self.redis.get(self.config.cache_key)
        if not cached_data:
            logger.warning("Кэш списка монет пуст. Запускаю принудительное обновление.")
            await self.update_coin_list_cache()
            cached_data = await self.redis.get(self.config.cache_key)
            if not cached_data:
                logger.error("Не удалось обновить кэш списка монет.")
                return []
        
        return [CoinInfo.model_validate(item) for item in json.loads(cached_data)]

    async def find_coin(self, query: str) -> Optional[CoinInfo]:
        """
        Выполняет интеллектуальный нечеткий поиск монеты в справочнике.
        """
        query = query.strip().lower()
        if not query:
            return None

        all_coins = await self.get_all_coins()
        if not all_coins:
            return None

        # Создаем словарь для поиска, где ключ - тикер, и словарь, где ключ - имя
        ticker_map = {coin.coin.lower(): coin for coin in all_coins}
        name_map = {coin.name.lower(): coin for coin in all_coins}

        # Сначала ищем по точному совпадению тикера
        if query in ticker_map:
            return ticker_map[query]

        # Затем ищем по точному совпадению имени
        if query in name_map:
            return name_map[query]
            
        # Если точных совпадений нет, используем нечеткий поиск по именам
        best_match_name = process.extractOne(
            query, name_map.keys(), scorer=fuzz.WRatio, score_cutoff=self.config.search_score_cutoff
        )

        if best_match_name:
            match_key, _, _ = best_match_name
            return name_map[match_key]
            
        logger.warning(f"Не найдено совпадений для запроса монеты '{query}'.")
        return None
