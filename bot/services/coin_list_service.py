# src/bot/services/coin_list_service.py
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from bot.config.settings import CoinListServiceConfig
from bot.utils.http_client import HttpClient
from bot.utils.keys import KeyFactory


# Hardcoded fallback для популярных монет (гарантирует работу даже без API)
POPULAR_COINS_MAPPING = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "USDC": "usd-coin",
    "XRP": "ripple",
    "STETH": "staked-ether",
    "TON": "the-open-network",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "TRX": "tron",
    "AVAX": "avalanche-2",
    "WBTC": "wrapped-bitcoin",
    "SHIB": "shiba-inu",
    "LINK": "chainlink",
    "DOT": "polkadot",
    "BCH": "bitcoin-cash",
    "DAI": "dai",
    "LEO": "leo-token",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "MATIC": "matic-network",
    "NEAR": "near",
    "ICP": "internet-computer",
    "APT": "aptos",
    "ETC": "ethereum-classic",
    "ATOM": "cosmos",
    "XLM": "stellar",
    "OKB": "okb",
    "XMR": "monero",
    "HBAR": "hedera-hashgraph",
    "FIL": "filecoin",
    "CRO": "crypto-com-chain",
    "ARB": "arbitrum",
    "OP": "optimism",
    "MNT": "mantle",
    "VET": "vechain",
    "AAVE": "aave",
    "MKR": "maker",
    "GRT": "the-graph",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "AXS": "axie-infinity",
    "ALGO": "algorand",
    "THETA": "theta-token",
    "FTM": "fantom",
    "EOS": "eos",
    "ZEC": "zcash",
    "EGLD": "elrond-erd-2",
    "RUNE": "thorchain",
    "XTZ": "tezos",
    "CHZ": "chiliz",
    "QNT": "quant-network",
    "CAKE": "pancakeswap-token",
    "FLOW": "flow",
    "NEO": "neo",
    "KCS": "kucoin-shares",
}


class CoinData(BaseModel):
    id: str
    symbol: str
    name: str


class CoinListService:
    def __init__(
        self,
        redis_client: Redis,
        http_client: HttpClient,
        config: CoinListServiceConfig,
    ):
        self.redis = redis_client
        self.http_client = http_client
        self.config = config
        self.keys = KeyFactory
        self.fallback_path = Path(self.config.fallback_file_path)
        logger.info("Сервис CoinListService инициализирован.")

    async def update_coin_list(self) -> int:
        logger.info("Запуск задачи обновления списка криптовалют...")
        
        coins = await self._fetch_from_sources()
        
        if not coins:
            logger.warning("Не удалось получить данные из онлайн-источников. Загрузка из резервного файла.")
            coins = self._load_fallback_coins()

        if not coins:
            logger.critical("Обновление списка монет не удалось: все источники недоступны.")
            return 0

        validated_coins = self._normalize_and_validate(coins)
        
        await self._cache_and_index_coins(validated_coins)
        await self._create_fallback_backup(validated_coins)

        logger.success(f"Список из {len(validated_coins)} криптовалют успешно обновлен.")
        return len(validated_coins)

    async def _fetch_from_sources(self) -> List[Dict[str, str]]:
        logger.debug("Попытка получения списка монет из CoinGecko...")
        try:
            url = f"{self.http_client.config.coingecko_api_base}{self.http_client.config.coins_list_endpoint}"
            data = await self.http_client.get(url)
            if data and isinstance(data, list):
                return data
        except Exception as e:
            logger.warning(f"Ошибка при получении данных от CoinGecko: {e}.")
        
        return []

    def _normalize_and_validate(self, coins: List[Dict[str, str]]) -> List[CoinData]:
        seen_symbols = set()
        validated_coins = []
        for coin_data in coins:
            try:
                coin = CoinData.model_validate(coin_data)
                symbol_upper = coin.symbol.upper()
                if symbol_upper not in seen_symbols:
                    validated_coins.append(coin)
                    seen_symbols.add(symbol_upper)
            except ValidationError as e:
                logger.trace(f"Ошибка валидации данных монеты: {coin_data}. Ошибка: {e}")
        
        validated_coins.sort(key=lambda c: c.symbol)
        return validated_coins

    async def _cache_and_index_coins(self, coins: List[CoinData]):
        try:
            pipe = self.redis.pipeline()
            
            coins_json = json.dumps([c.model_dump() for c in coins], ensure_ascii=False)
            pipe.set(self.keys.get_coin_list_key(), coins_json)
            
            # Основной индекс из API
            symbol_to_id_map = {c.symbol.upper(): c.id for c in coins}
            id_to_symbol_map = {c.id: c.symbol.upper() for c in coins}
            
            # Добавляем hardcoded популярные монеты (перезаписываем если есть конфликт)
            symbol_to_id_map.update(POPULAR_COINS_MAPPING)
            for symbol, coin_id in POPULAR_COINS_MAPPING.items():
                id_to_symbol_map[coin_id] = symbol
            
            pipe.delete(self.keys.get_coin_index_symbol_to_id_key())
            pipe.delete(self.keys.get_coin_index_id_to_symbol_key())
            
            if symbol_to_id_map:
                pipe.hset(self.keys.get_coin_index_symbol_to_id_key(), mapping=symbol_to_id_map)
            if id_to_symbol_map:
                pipe.hset(self.keys.get_coin_index_id_to_symbol_key(), mapping=id_to_symbol_map)

            await pipe.execute()
        except Exception as e:
            logger.exception(f"Ошибка при кэшировании или индексации: {e}")

    async def get_coin_list(self) -> List[CoinData]:
        try:
            coins_json = await self.redis.get(self.keys.get_coin_list_key())
            if coins_json:
                return [CoinData.model_validate(c) for c in json.loads(coins_json)]
        except Exception as e:
            logger.error(f"Ошибка при получении списка из Redis: {e}")
        
        logger.warning("Используем fallback.")
        fallback_data = self._load_fallback_coins()
        return [CoinData.model_validate(c) for c in fallback_data]

    async def get_coin_id_by_symbol(self, symbol: str) -> Optional[str]:
        """Находит coin_id по символу с fallback на hardcoded mapping"""
        symbol_upper = symbol.upper()
        
        # Сначала проверяем hardcoded
        if symbol_upper in POPULAR_COINS_MAPPING:
            logger.debug(f"Hardcoded mapping: {symbol_upper} -> {POPULAR_COINS_MAPPING[symbol_upper]}")
            return POPULAR_COINS_MAPPING[symbol_upper]
        
        # Потом Redis
        try:
            coin_id = await self.redis.hget(self.keys.get_coin_index_symbol_to_id_key(), symbol_upper)
            if coin_id:
                logger.debug(f"Redis mapping: {symbol_upper} -> {coin_id}")
                return coin_id
        except Exception as e:
            logger.error(f"Ошибка Redis при поиске ID для {symbol}: {e}")
        
        return None

    async def get_symbol_by_coin_id(self, coin_id: str) -> Optional[str]:
        """Находит символ по coin_id"""
        try:
            symbol = await self.redis.hget(self.keys.get_coin_index_id_to_symbol_key(), coin_id)
            if symbol:
                return symbol
        except Exception as e:
            logger.error(f"Ошибка Redis при поиске символа для {coin_id}: {e}")
        
        # Fallback на hardcoded mapping
        for sym, cid in POPULAR_COINS_MAPPING.items():
            if cid == coin_id:
                return sym
        
        return None

    def _load_fallback_coins(self) -> List[Dict[str, str]]:
        if not self.fallback_path.exists():
            logger.error(f"Резервный файл {self.fallback_path} не найден.")
            return []
        try:
            with open(self.fallback_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f"Не удалось загрузить резервный файл: {e}")
            return []

    async def _create_fallback_backup(self, coins: List[CoinData]):
        try:
            coins_dict = [c.model_dump() for c in coins]
            
            def _write_sync():
                self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.fallback_path, 'w', encoding='utf-8') as f:
                    json.dump(coins_dict, f, ensure_ascii=False, indent=2)
            
            await asyncio.to_thread(_write_sync)
            logger.info(f"Резервная копия создана в {self.fallback_path}")
        except Exception as e:
            logger.error(f"Не удалось создать резервную копию: {e}")