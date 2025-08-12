# =================================================================================
# Файл: bot/services/market_data_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Центральный сервис для получения любых рыночных данных.
# ИСПРАВЛЕНИЕ: Исправлена критическая ошибка в конвертации хешрейта (умножение вместо деления).
# =================================================================================
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Literal
from math import ceil

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import Settings
from bot.utils.http_client import make_request
from bot.services.coin_list_service import CoinListService

logger = logging.getLogger(__name__)

Provider = Literal["coingecko", "cryptocompare"]
HALVING_INTERVAL = 210000
AVG_BLOCK_TIME_MINUTES = 10
INITIAL_BLOCK_REWARD = 50.0

class MarketDataService:
    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        settings: Settings,
        coin_list_service: CoinListService
    ):
        self.redis = redis
        self.http_session = http_session
        self.config = settings.market_data
        self.endpoints = settings.endpoints
        self.settings = settings
        self.coin_list = coin_list_service

    async def get_prices(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        # ... (код без изменений)
        try:
            prices = await self._fetch_prices_from_provider(coin_ids, self.config.primary_provider)
            coins_to_retry = [cid for cid, price in prices.items() if price is None]
            if coins_to_retry:
                fallback_prices = await self._fetch_prices_from_provider(coins_to_retry, self.config.fallback_provider)
                prices.update(fallback_prices)
            return prices
        except Exception:
            try:
                return await self._fetch_prices_from_provider(coin_ids, self.config.fallback_provider)
            except Exception:
                return {cid: None for cid in coin_ids}

    async def _fetch_prices_from_provider(self, coin_ids: List[str], provider: Provider) -> Dict[str, Optional[float]]:
        # ... (код без изменений)
        if provider == "coingecko":
            return await self._get_prices_coingecko(coin_ids)
        elif provider == "cryptocompare":
            return await self._get_prices_cryptocompare(coin_ids)
        raise ValueError(f"Неизвестный провайдер API: {provider}")

    async def _get_prices_coingecko(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        # ... (код без изменений)
        api_key = self.settings.COINGECKO_API_KEY.get_secret_value() if self.settings.COINGECKO_API_KEY else None
        headers = {'x-cg-pro-api-key': api_key} if api_key else {}
        base_url = self.endpoints.coingecko_api_pro_base if api_key else self.endpoints.coingecko_api_base
        url = f"{base_url}{self.endpoints.simple_price_endpoint}"
        params = {'ids': ','.join(coin_ids), 'vs_currencies': 'usd'}
        data = await make_request(self.http_session, url, params=params, headers=headers)
        result = {cid: None for cid in coin_ids}
        if data:
            for cid, price_data in data.items():
                result[cid] = price_data.get('usd')
        return result

    async def _get_prices_cryptocompare(self, coin_ids: List[str]) -> Dict[str, Optional[float]]:
        # ... (код без изменений)
        api_key = self.settings.CRYPTOCOMPARE_API_KEY.get_secret_value() if self.settings.CRYPTOCOMPARE_API_KEY else None
        if not api_key: return {cid: None for cid in coin_ids}
        headers = {'Authorization': f'Apikey {api_key}'}
        url = f"{self.endpoints.cryptocompare_api_base}{self.endpoints.cryptocompare_price_endpoint}"
        id_to_symbol_map, symbols_to_fetch = {}, []
        for cid in coin_ids:
            if coin := await self.coin_list.find_coin_by_query(cid):
                symbol = coin.symbol.upper()
                id_to_symbol_map[symbol] = cid
                symbols_to_fetch.append(symbol)
        if not symbols_to_fetch: return {cid: None for cid in coin_ids}
        params = {'fsyms': ','.join(symbols_to_fetch), 'tsyms': 'USD'}
        data = await make_request(self.http_session, url, params=params, headers=headers)
        result = {cid: None for cid in coin_ids}
        if data:
            for symbol, price_data in data.items():
                if original_id := id_to_symbol_map.get(symbol):
                    result[original_id] = price_data.get('USD')
        return result
        
    async def get_fear_and_greed_index(self) -> Optional[Dict]:
        data = await make_request(self.http_session, str(self.endpoints.fear_and_greed_api))
        return data['data'][0] if data and data.get('data') else None

    async def get_halving_info(self) -> Optional[Dict[str, Any]]:
        # ... (код без изменений)
        try:
            current_height = int(await make_request(self.http_session, str(self.endpoints.mempool_space_tip_height), response_type="text"))
            halving_cycle = current_height // HALVING_INTERVAL
            next_halving_block = (halving_cycle + 1) * HALVING_INTERVAL
            blocks_remaining = next_halving_block - current_height
            estimated_date = datetime.now(timezone.utc) + timedelta(minutes=blocks_remaining * AVG_BLOCK_TIME_MINUTES)
            progress = (current_height % HALVING_INTERVAL) / HALVING_INTERVAL * 100
            return {"progressPercent": progress, "remainingBlocks": blocks_remaining, "estimated_date": estimated_date.strftime('%d.%m.%Y')}
        except Exception as e:
            logger.error(f"Не удалось вычислить данные о халвинге: {e}", exc_info=True)
            return None

    async def get_btc_price_usd(self) -> Optional[float]:
        prices = await self.get_prices(['bitcoin'])
        return prices.get('bitcoin')

    async def get_network_hashrate_ths(self) -> Optional[float]:
        """Получает текущий хешрейт сети Bitcoin в TH/s."""
        # API возвращает значение в GH/s
        hashrate_ghs_str = await make_request(self.http_session, str(self.endpoints.blockchain_info_hashrate), response_type="text")
        if hashrate_ghs_str and hashrate_ghs_str.replace('.', '', 1).isdigit():
            # ИСПРАВЛЕНО: Для конвертации из GH/s в TH/s нужно делить на 1000.
            return float(hashrate_ghs_str) / 1000
        return None

    async def get_block_reward_btc(self) -> Optional[float]:
        # ... (код без изменений)
        try:
            current_height = int(await make_request(self.http_session, str(self.endpoints.mempool_space_tip_height), response_type="text"))
            halving_count = current_height // HALVING_INTERVAL
            return INITIAL_BLOCK_REWARD / (2 ** halving_count)
        except Exception:
            return 3.125