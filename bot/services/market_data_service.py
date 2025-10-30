# src/bot/services/market_data_service.py

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from bot.config.settings import MarketDataServiceConfig
from bot.services.coin_list_service import CoinListService
from bot.utils.http_client import HttpClient
from bot.utils.keys import KeyFactory


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

    def __init__(
        self,
        redis_client: Redis,
        http_client: HttpClient,
        coin_list_service: CoinListService,
        config: MarketDataServiceConfig,
    ):
        self.redis = redis_client
        self.http_client = http_client
        self.coin_list_service = coin_list_service
        self.config = config
        self.keys = KeyFactory
        logger.info("Сервис MarketDataService инициализирован.")

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """
        Получает цены, используя основного провайдера и переключаясь на резервного при неудаче.
        """
        try:
            prices = await self._fetch_prices_from_provider(coin_ids, self.config.primary_provider)
            
            coins_to_retry = [cid for cid, price in prices.items() if price is None]
            if coins_to_retry:
                logger.warning(f"Не удалось получить цены для {coins_to_retry} через основного провайдера. Попытка через резервного.")
                fallback_prices = await self._fetch_prices_from_provider(coins_to_retry, self.config.fallback_provider)
                prices.update(fallback_prices)
            return prices
        except Exception as e:
            logger.error(f"Ошибка при запросе к основному провайдеру ({self.config.primary_provider}): {e}. Переключение на резервного.")
            try:
                return await self._fetch_prices_from_provider(coin_ids, self.config.fallback_provider)
            except Exception as fallback_e:
                logger.critical(f"Резервный провайдер ({self.config.fallback_provider}) также не доступен: {fallback_e}")
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
        params = {'ids': ','.join(coin_ids), 'vs_currencies': 'usd'}
        data = await self.http_client.get(
            f"{self.http_client.config.coingecko_api_base}{self.http_client.config.simple_price_endpoint}",
            params=params
        )
        result = {cid: None for cid in coin_ids}
        if data:
            for cid, price_data in data.items():
                result[cid] = float(price_data['usd']) if 'usd' in price_data else None
        return result

    async def _get_prices_cryptocompare(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """Получает цены от CryptoCompare."""
        symbols_to_fetch, id_to_symbol_map = [], {}
        for cid in coin_ids:
            symbol = await self.coin_list_service.get_symbol_by_coin_id(cid)
            if symbol:
                symbols_to_fetch.append(symbol.upper())
                id_to_symbol_map[symbol.upper()] = cid
        
        if not symbols_to_fetch:
            return {cid: None for cid in coin_ids}

        params = {'fsyms': ','.join(symbols_to_fetch), 'tsyms': 'USD'}
        data = await self.http_client.get(
            f"{self.http_client.config.cryptocompare_api_base}{self.http_client.config.cryptocompare_price_endpoint}",
            params=params
        )
        
        result = {cid: None for cid in coin_ids}
        if data and "Response" not in data:
            for symbol, price_data in data.items():
                if original_id := id_to_symbol_map.get(symbol):
                    result[original_id] = float(price_data['USD']) if 'USD' in price_data else None
        return result

    async def get_fear_and_greed_index(self) -> Optional[FearAndGreedData]:
        """Получает 'Индекс страха и жадности'."""
        try:
            data = await self.http_client.get(str(self.http_client.config.fear_and_greed_api))
            return FearAndGreedResponse.model_validate(data).data[0]
        except (ValidationError, IndexError, Exception) as e:
            logger.error(f"Не удалось получить 'Индекс страха и жадности': {e}")
            return None

    async def get_halving_info(self) -> Optional[HalvingInfo]:
        """Рассчитывает информацию о следующем халвинге Bitcoin."""
        try:
            HALVING_INTERVAL = 210000
            AVG_BLOCK_TIME_MINUTES = 10

            tip_height_str = await self.http_client.get(str(self.http_client.config.mempool_space_tip_height))
            current_height = int(tip_height_str)

            halving_cycle = current_height // HALVING_INTERVAL
            next_halving_block = (halving_cycle + 1) * HALVING_INTERVAL
            blocks_remaining = next_halving_block - current_height
            estimated_date = datetime.now(timezone.utc) + timedelta(minutes=blocks_remaining * AVG_BLOCK_TIME_MINUTES)
            progress = (current_height % HALVING_INTERVAL) / HALVING_INTERVAL * 100
            
            return HalvingInfo(
                progressPercent=progress,
                remainingBlocks=blocks_remaining,
                estimated_date=estimated_date.strftime('%d.%m.%Y')
            )
        except (ValueError, Exception) as e:
            logger.error(f"Не удалось вычислить данные о халвинге: {e}")
            return None

    async def get_btc_network_status(self) -> Optional[NetworkStatus]:
        """Получает статус сети Bitcoin."""
        try:
            data = await self.http_client.get(str(self.http_client.config.mempool_space_difficulty_adjustment))
            if not data:
                return None
            
            hashrate_ehs = data.get('currentHashrate', 0) / 1e18
            difficulty_change = data.get('difficultyChange', 0)
            estimated_retarget_timestamp = data.get('estimatedRetargetDate', 0) / 1000
            estimated_retarget_date = datetime.fromtimestamp(estimated_retarget_timestamp, tz=timezone.utc).strftime('%d.%m.%Y')
            
            return NetworkStatus(
                hashrate_ehs=hashrate_ehs,
                difficulty_change=difficulty_change,
                estimated_retarget_date=estimated_retarget_date
            )
        except Exception as e:
            logger.error(f"Не удалось получить статус сети BTC: {e}")
            return None

    async def get_top_n_coins(self, limit: int) -> List[Dict[str, Any]]:
        """Получает топ N монет по рыночной капитализации."""
        cache_key = self.keys.get_top_coins_cache_key()
        try:
            if cached_data := await self.redis.get(cache_key):
                logger.debug(f"Cache hit for top {limit} coins.")
                all_coins = json.loads(cached_data)
                return [TopCoin.model_validate(item).model_dump() for item in all_coins[:limit]]
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Кэш топ-монет поврежден ({e}), будет запрошен заново.")

        params = {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': limit, 'page': 1}
        data = await self.http_client.get(
            f"{self.http_client.config.coingecko_api_base}{self.http_client.config.coins_markets_endpoint}",
            params=params
        )

        if data:
            try:
                validated_data = [TopCoin.model_validate(item).model_dump() for item in data]
                if limit >= self.config.top_n_coins:
                    await self.redis.set(cache_key, json.dumps(validated_data), ex=3600)
                return validated_data
            except ValidationError as e:
                logger.error(f"Ошибка валидации данных топ-монет от API: {e}")
        
        return []