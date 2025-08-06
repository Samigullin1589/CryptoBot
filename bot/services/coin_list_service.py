# =================================================================================
# Файл: bot/services/coin_list_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для управления списком криптовалют.
# ИСПРАВЛЕНИЕ: Добавлен 'from __future__ import annotations' для решения
# проблемы циклического импорта.
# =================================================================================

from __future__ import annotations # <--- ИСПРАВЛЕНО
import json
import logging
from typing import List, Dict, Any, Optional

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import CoinListServiceConfig, EndpointsConfig
from bot.utils.models import Coin

logger = logging.getLogger(__name__)

class CoinListService:
    """
    Управляет получением, кэшированием и предоставлением списка криптовалют.
    """
    _COIN_LIST_CACHE_KEY = "cache:coin_list"

    def __init__(
        self,
        redis: Redis,
        http_session: aiohttp.ClientSession,
        config: CoinListServiceConfig,
        endpoints: EndpointsConfig,
    ):
        self.redis = redis
        self.http_session = http_session
        self.config = config
        self.endpoints = endpoints
        self._coin_list_url = f"{endpoints.coingecko_api_base}{endpoints.coins_list_endpoint}"

    async def _fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """Загружает сырой список монет с API CoinGecko."""
        logger.info(f"Загрузка свежего списка монет с API: {self._coin_list_url}")
        try:
            async with self.http_session.get(self._coin_list_url) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Успешно загружено {len(data)} монет с API.")
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP клиента при загрузке списка монет: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось декодировать JSON ответ от API списка монет: {e}")
        return None

    async def _load_fallback_data(self) -> List[Dict[str, Any]]:
        """Загружает список монет из локального резервного файла."""
        logger.warning(f"Попытка загрузить список монет из резервного файла: {self.config.fallback_file_path}")
        try:
            with open(self.config.fallback_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Успешно загружено {len(data)} монет из резервного файла.")
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Не удалось загрузить или разобрать резервный файл списка монет: {e}")
            return []

    async def update_coin_list(self) -> None:
        """
        Обновляет список монет в кэше Redis.
        """
        logger.info("Запуск планового обновления списка монет.")
        coin_data = await self._fetch_from_api()

        if coin_data is None:
            logger.warning("Загрузка с API не удалась, попытка загрузки из резервного файла.")
            coin_data = await self._load_fallback_data()

        if coin_data:
            try:
                coins = [Coin.model_validate(coin) for coin in coin_data]
                coins_to_cache = [c.model_dump(mode='json') for c in coins]
                await self.redis.set(self._COIN_LIST_CACHE_KEY, json.dumps(coins_to_cache))
                logger.info(f"Успешно обновлено и кэшировано {len(coins)} монет.")
            except Exception as e:
                logger.error(f"Не удалось валидировать или кэшировать данные монет: {e}")
        else:
            logger.error("Не удалось обновить список монет ни с API, ни из резервного файла.")

    async def get_all_coins(self) -> List[Coin]:
        """
        Получает список всех монет из кэша.
        """
        cached_data = await self.redis.get(self._COIN_LIST_CACHE_KEY)
        if cached_data:
            try:
                coins_data = json.loads(cached_data)
                return [Coin.model_validate(c) for c in coins_data]
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Ошибка декодирования кэшированного списка монет: {e}. Запускаю обновление.")

        logger.warning("Кэш списка монет пуст или невалиден. Запускаю немедленное обновление.")
        await self.update_coin_list()

        cached_data_after_update = await self.redis.get(self._COIN_LIST_CACHE_KEY)
        if cached_data_after_update:
            return [Coin.model_validate(c) for c in json.loads(cached_data_after_update)]

        logger.error("Не удалось получить список монет даже после попытки обновления.")
        return []
