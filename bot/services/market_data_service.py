# =================================================================================
# Файл: bot/services/market_data_service.py (ВЕРСИЯ "Distinguished Engineer" - ОТКАЗОУСТОЙЧИВАЯ С CRYPTOCOMPARE)
# Описание: Центральный сервис для получения любых рыночных данных с
#           поддержкой CryptoCompare как резервного источника.
# =================================================================================
import logging
from typing import List, Optional, Dict, Any, Literal

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import MarketDataServiceConfig, EndpointsConfig, Settings
from bot.utils.http_client import make_request
from bot.services.coin_list_service import CoinListService # Важный импорт для сопоставления

logger = logging.getLogger(__name__)

Provider = Literal["coingecko", "cryptocompare"]

class MarketDataService:
    """
    Отвечает за получение и кэширование всех рыночных данных,
    реализуя стратегию отказоустойчивости с основным и резервным API.
    """
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        settings: Settings,
        coin_list_service: CoinListService # Добавляем зависимость
    ):
        self.redis = redis
        self.http_session = http_session
        self.config = settings.market_data
        self.endpoints = settings.endpoints
        self.settings = settings
        self.coin_list = coin_list_service

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        """
        Получает цены, сначала пытаясь использовать основной API,
        а при неудаче - резервный.
        """
        try:
            prices = await self._fetch_prices_from_provider(coin_ids, self.config.primary_provider)
            # Если основной провайдер вернул пустые данные для некоторых монет, пробуем резервный
            coins_to_retry = [cid for cid, price in prices.items() if price is None]
            if coins_to_retry:
                logger.warning(f"Основной API не вернул данные для {coins_to_retry}. Пробую резервный.")
                fallback_prices = await self._fetch_prices_from_provider(coins_to_retry, self.config.fallback_provider)
                prices.update(fallback_prices)
            return prices

        except Exception as e:
            logger.error(f"Основной API ({self.config.primary_provider}) не ответил: {e}. Переключаюсь на резервный.")
            try:
                return await self._fetch_prices_from_provider(coin_ids, self.config.fallback_provider)
            except Exception as e_fallback:
                logger.critical(f"Резервный API ({self.config.fallback_provider}) тоже не ответил: {e_fallback}")
                return {cid: None for cid in coin_ids}

    async def _fetch_prices_from_provider(self, coin_ids: List[str], provider: Provider) -> Dict[str, Optional[float]]:
        if provider == "coingecko":
            return await self._get_prices_coingecko(coin_ids)
        elif provider == "cryptocompare":
            return await self._get_prices_cryptocompare(coin_ids)
        else:
            raise ValueError(f"Неизвестный провайдер API: {provider}")

    async def _get_prices_coingecko(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        api_key = self.settings.COINGECKO_API_KEY.get_secret_value() if self.settings.COINGECKO_API_KEY else None
        headers = {'x-cg-pro-api-key': api_key} if api_key else {}
        base_url = self.endpoints.coingecko_api_pro_base if api_key else self.endpoints.coingecko_api_base
        url = f"{base_url}{self.endpoints.simple_price_endpoint}"
        
        params = {'ids': ','.join(coin_ids), 'vs_currencies': 'usd'}
        data = await make_request(self.http_session, url, params=params, headers=headers)
        
        # Возвращаем словарь с None для всех запрошенных ID, если API не вернул данные
        result = {cid: None for cid in coin_ids}
        if data:
            for cid, price_data in data.items():
                result[cid] = price_data.get('usd')
        return result

    async def _get_prices_cryptocompare(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        api_key = self.settings.CRYPTOCOMPARE_API_KEY.get_secret_value() if self.settings.CRYPTOCOMPARE_API_KEY else None
        if not api_key:
            logger.error("API-ключ для CryptoCompare не предоставлен. Резервный функционал недоступен.")
            return {cid: None for cid in coin_ids}

        headers = {'Authorization': f'Apikey {api_key}'}
        url = f"{self.endpoints.cryptocompare_api_base}{self.endpoints.cryptocompare_price_endpoint}"

        # CryptoCompare использует символы (BTC), а не ID (bitcoin).
        # Нам нужно сопоставить ID с символами.
        id_to_symbol_map = {}
        symbols_to_fetch = []
        for cid in coin_ids:
            coin = await self.coin_list.find_coin_by_query(cid)
            if coin:
                symbol = coin.symbol.upper()
                id_to_symbol_map[symbol] = cid
                symbols_to_fetch.append(symbol)
        
        if not symbols_to_fetch:
            return {cid: None for cid in coin_ids}

        params = {'fsyms': ','.join(symbols_to_fetch), 'tsyms': 'USD'}
        data = await make_request(self.http_session, url, params=params, headers=headers)

        result = {cid: None for cid in coin_ids}
        if data:
            for symbol, price_data in data.items():
                original_id = id_to_symbol_map.get(symbol)
                if original_id:
                    result[original_id] = price_data.get('USD')
        return result

    # --- Остальные методы ---
    async def get_fear_and_greed_index(self) -> Optional[Dict]:
        data = await make_request(self.http_session, str(self.endpoints.fear_and_greed_api))
        if data and data.get('data'):
            return data['data'][0]
        return None

    async def get_halving_info(self) -> Optional[Dict]:
        return await make_request(self.http_session, "https://mempool.space/api/v1/difficulty-adjustment")
        
    async def get_btc_network_status(self) -> Optional[Dict]:
        hashrate_ths = await make_request(self.http_session, "https://blockchain.info/q/hashrate", response_type="text")
        if hashrate_ths:
            return {'hashrate_ehs': float(hashrate_ths) / 1_000_000}
        return None