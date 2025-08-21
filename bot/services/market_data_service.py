# bot/services/market_data_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Централизованный сервис для получения рыночных данных из нескольких
# источников с отказоустойчивостью и кэшированием в Redis.

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from bot.config.settings import settings
from bot.services.coin_list_service import CoinListService
from bot.utils.dependencies import get_redis_client
from bot.utils.http_client import http_session
from bot.utils.keys import KeyFactory

# --- Pydantic модели для валидации ответов API ---

class FearAndGreedData(BaseModel):
    value: str
    value_classification: str

class FearAndGreedResponse(BaseModel):
    data: List[FearAndGreedData]

class HalvingInfo(BaseModel):
    progressPercent: float
    remainingBlocks: int
    estimated_date: str

class NetworkStatus(BaseModel):
    hashrate_ehs: float
    difficulty_change: float
    estimated_retarget_date: str

class TopCoin(BaseModel):
    id: str
    symbol: str
    name: str
    current_price: Optional[float] = None
    market_cap: Optional[int] = None
    price_change_percentage_24h: Optional[float] = None
    ath: Optional[float] = None


Provider = Literal["coingecko", "cryptocompare"]

class MarketDataService:
    """
    Агрегирует рыночные данные, обеспечивая отказоустойчивость
    и кэширование для минимизации обращений к внешним API.
    """

    def __init__(self, coin_list_service: CoinListService):
        self.redis: Redis = get_redis_client()
        self.coin_list_service = coin_list_service
        self.config = settings.MARKET_DATA
        self.keys = KeyFactory
        logger.info("Сервис MarketDataService инициализирован.")

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """
        Получает цены, используя основного провайдера и переключаясь на резервного при неудаче.
        """
        try:
            prices = await self._fetch_prices_from_provider(coin_ids, self.config.PRIMARY_PROVIDER)
            
            coins_to_retry = [cid for cid, price in prices.items() if price is None]
            if coins_to_retry:
                logger.warning(f"Не удалось получить цены для {coins_to_retry} через основного провайдера. Попытка через резервного.")
                fallback_prices = await self._fetch_prices_from_provider(coins_to_retry, self.config.FALLBACK_PROVIDER)
                prices.update(fallback_prices)
            return prices
        except Exception as e:
            logger.error(f"Ошибка при запросе к основному провайдеру ({self.config.PRIMARY_PROVIDER}): {e}. Переключение на резервного.")
            try:
                return await self._fetch_prices_from_provider(coin_ids, self.config.FALLBACK_PROVIDER)
            except Exception as fallback_e:
                logger.critical(f"Резервный провайдер ({self.config.FALLBACK_PROVIDER}) также не доступен: {fallback_e}")
                return {cid: None for cid in coin_ids}

    async def _fetch_prices_from_provider(self, coin_ids: List[str], provider: Provider) -> Dict[str, Optional[float]]:
        """Маршрутизирует запрос к соответствующему методу провайдера."""
        if not coin_ids:
            return {}
        if provider == "coingecko":
            return await self._get_prices_coingecko(coin_ids)
        if provider == "cryptocompare":
            return await self._get_prices_cryptocompare(coin_ids)
        raise ValueError(f"Неизвестный провайдер API: {provider}")

    async def _get_prices_coingecko(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Получает цены от CoinGecko."""
        api_key = settings.COINGECKO_API_KEY.get_secret_value() if settings.COINGECKO_API_KEY else None
        headers = {'x-cg-pro-api-key': api_key} if api_key else {}
        base_url = self.config.COINGECKO_API_PRO_BASE if api_key else self.config.COINGECKO_API_BASE
        url = f"{base_url}/simple/price"
        params = {'ids': ','.join(coin_ids), 'vs_currencies': 'usd'}
        
        try:
            async with http_session() as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
            
            result = {cid: None for cid in coin_ids}
            if data:
                for cid, price_data in data.items():
                    result[cid] = float(price_data['usd']) if 'usd' in price_data else None
            return result
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Ошибка при запросе к CoinGecko: {e}")
            return {cid: None for cid in coin_ids}

    async def _get_prices_cryptocompare(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Получает цены от CryptoCompare."""
        api_key = settings.CRYPTOCOMPARE_API_KEY.get_secret_value() if settings.CRYPTOCOMPARE_API_KEY else None
        if not api_key:
            logger.warning("CRYPTOCOMPARE_API_KEY не установлен. Пропуск запроса.")
            return {cid: None for cid in coin_ids}
            
        headers = {'Authorization': f'Apikey {api_key}'}
        url = f"{self.config.CRYPTOCOMPARE_API_BASE}/data/pricemulti"
        
        symbols_to_fetch, id_to_symbol_map = [], {}
        for cid in coin_ids:
            symbol = await self.coin_list_service.get_symbol_by_coin_id(cid)
            if symbol:
                symbols_to_fetch.append(symbol)
                id_to_symbol_map[symbol] = cid
        
        if not symbols_to_fetch:
            return {cid: None for cid in coin_ids}
            
        params = {'fsyms': ','.join(symbols_to_fetch), 'tsyms': 'USD'}
        try:
            async with http_session() as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

            result = {cid: None for cid in coin_ids}
            if data and "Response" not in data:
                for symbol, price_data in data.items():
                    if original_id := id_to_symbol_map.get(symbol):
                        result[original_id] = float(price_data['USD']) if 'USD' in price_data else None
            return result
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Ошибка при запросе к CryptoCompare: {e}")
            return {cid: None for cid in coin_ids}

    async def get_fear_and_greed_index(self) -> Optional[FearAndGreedData]:
        """Получает 'Индекс страха и жадности'."""
        try:
            async with http_session() as client:
                response = await client.get(self.config.FEAR_AND_GREED_API_URL)
                response.raise_for_status()
                return FearAndGreedResponse.model_validate(response.json()).data[0]
        except (httpx.RequestError, httpx.HTTPStatusError, IndexError, ValidationError) as e:
            logger.error(f"Не удалось получить 'Индекс страха и жадности': {e}")
            return None

    async def get_halving_info(self) -> Optional[HalvingInfo]:
        """Рассчитывает информацию о следующем халвинге Bitcoin."""
        try:
            async with http_session() as client:
                response = await client.get(self.config.MEMPOOL_TIP_HEIGHT_URL)
                response.raise_for_status()
                current_height = int(response.text)

            halving_cycle = current_height // self.config.HALVING_INTERVAL
            next_halving_block = (halving_cycle + 1) * self.config.HALVING_INTERVAL
            blocks_remaining = next_halving_block - current_height
            estimated_date = datetime.now(timezone.utc) + timedelta(minutes=blocks_remaining * self.config.AVG_BLOCK_TIME_MINUTES)
            progress = (current_height % self.config.HALVING_INTERVAL) / self.config.HALVING_INTERVAL * 100
            
            return HalvingInfo(
                progressPercent=progress,
                remainingBlocks=blocks_remaining,
                estimated_date=estimated_date.strftime('%d.%m.%Y')
            )
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            logger.error(f"Не удалось вычислить данные о халвинге: {e}")
            return None

    async def get_top_coins_by_market_cap(self, limit: int = 30) -> List[TopCoin]:
        """Получает топ монет по капитализации из кэша или через API."""
        cache_key = self.keys.top_coins_cache(limit)
        try:
            if cached_data := await self.redis.get(cache_key):
                return [TopCoin.model_validate(item) for item in json.loads(cached_data)]
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Кэш топ-монет поврежден ({e}), будет запрошен заново.")

        api_key = settings.COINGECKO_API_KEY.get_secret_value() if settings.COINGECKO_API_KEY else None
        headers = {'x-cg-pro-api-key': api_key} if api_key else {}
        base_url = self.config.COINGECKO_API_PRO_BASE if api_key else self.config.COINGECKO_API_BASE
        url = f"{base_url}/coins/markets"
        params = {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': limit, 'page': 1}
        
        try:
            async with http_session() as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = [TopCoin.model_validate(item) for item in response.json()]
            
            await self.redis.set(cache_key, json.dumps([c.model_dump() for c in data]), ex=3600) # Кэш на 1 час
            return data
        except (httpx.RequestError, httpx.HTTPStatusError, ValidationError) as e:
            logger.error(f"Не удалось получить топ монет: {e}")
            return []