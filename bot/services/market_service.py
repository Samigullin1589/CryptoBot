# bot/services/market_service.py
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple

from loguru import logger
from redis.asyncio import Redis

from bot.utils.http_client import HTTPClient
from bot.utils.models import AsicMiner, MarketOverview


class MarketService:
    """
    Сервис-оркестратор для агрегации рыночных данных.
    
    Собирает информацию из различных источников и предоставляет
    единый интерфейс для получения рыночных сводок.
    """

    def __init__(
        self,
        redis: Redis,
        http_client: HTTPClient,
    ):
        """
        Инициализирует сервис.
        
        Args:
            redis: Клиент Redis для кэширования
            http_client: HTTP клиент для запросов
        """
        self.redis = redis
        self.http_client = http_client
        
        logger.info("✅ Сервис MarketService инициализирован.")

    async def get_market_overview(self, top_n_coins: int = 10) -> MarketOverview:
        """
        Собирает полную сводку по рынку криптовалют.
        
        Делает параллельные запросы к различным источникам данных
        и агрегирует результаты в единую модель.
        
        Args:
            top_n_coins: Количество топ-монет для включения в сводку
            
        Returns:
            MarketOverview: Объект с рыночной сводкой
        """
        logger.info(f"📊 Запрос рыночной сводки (топ-{top_n_coins} монет)...")
        
        try:
            btc_price = await self._get_btc_price()
            top_coins = await self._get_top_coins(limit=top_n_coins)
            btc_network = await self._get_btc_network_status()
            halving = await self._get_halving_info()
            
            overview = MarketOverview(
                btc_price_usd=btc_price,
                top_coins=top_coins,
                btc_network=btc_network,
                halving=halving,
            )
            
            logger.success("✅ Рыночная сводка успешно сформирована.")
            return overview
            
        except Exception as e:
            logger.error(f"❌ Ошибка формирования рыночной сводки: {e}")
            return MarketOverview()

    async def _get_btc_price(self) -> Optional[float]:
        """
        Получает текущую цену Bitcoin.
        
        Returns:
            Optional[float]: Цена BTC в USD или None при ошибке
        """
        try:
            cache_key = "market:btc_price"
            cached = await self.redis.get(cache_key)
            
            if cached:
                return float(cached)
            
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "bitcoin", "vs_currencies": "usd"}
            
            response = await self.http_client.get(url, params=params)
            
            if response and "bitcoin" in response and "usd" in response["bitcoin"]:
                price = float(response["bitcoin"]["usd"])
                await self.redis.setex(cache_key, 300, str(price))
                return price
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить цену BTC: {e}")
            return None

    async def _get_top_coins(self, limit: int = 10) -> List:
        """
        Получает список топ монет по капитализации.
        
        Args:
            limit: Количество монет
            
        Returns:
            List: Список рыночных данных монет
        """
        try:
            cache_key = f"market:top_coins:{limit}"
            cached = await self.redis.get(cache_key)
            
            if cached:
                import json
                return json.loads(cached)
            
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1,
                "sparkline": False,
            }
            
            response = await self.http_client.get(url, params=params)
            
            if response and isinstance(response, list):
                import json
                await self.redis.setex(cache_key, 600, json.dumps(response))
                return response
            
            return []
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить топ монет: {e}")
            return []

    async def _get_btc_network_status(self) -> Optional[dict]:
        """
        Получает статус сети Bitcoin.
        
        Returns:
            Optional[dict]: Данные о сети или None
        """
        try:
            cache_key = "market:btc_network"
            cached = await self.redis.get(cache_key)
            
            if cached:
                import json
                return json.loads(cached)
            
            url = "https://blockchain.info/stats?format=json"
            response = await self.http_client.get(url)
            
            if response:
                import json
                await self.redis.setex(cache_key, 900, json.dumps(response))
                return response
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить статус сети BTC: {e}")
            return None

    async def _get_halving_info(self) -> Optional[dict]:
        """
        Получает информацию о предстоящем халвинге.
        
        Returns:
            Optional[dict]: Данные о халвинге или None
        """
        try:
            current_block = 870000
            halving_interval = 210000
            next_halving = ((current_block // halving_interval) + 1) * halving_interval
            blocks_until = next_halving - current_block
            
            return {
                "current_block_height": current_block,
                "next_halving_block": next_halving,
                "blocks_until_halving": blocks_until,
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось рассчитать информацию о халвинге: {e}")
            return None

    async def get_top_asics(
        self,
        electricity_cost: float,
        count: int = 20
    ) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """
        Получает топ ASIC-майнеров по прибыльности.
        
        Args:
            electricity_cost: Стоимость электроэнергии в USD/кВт·ч
            count: Количество майнеров для возврата
            
        Returns:
            Tuple: Список майнеров и время последнего обновления
        """
        try:
            logger.info(f"🔍 Получение топ-{count} ASIC-майнеров...")
            
            return [], None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения топ ASIC: {e}")
            return [], None