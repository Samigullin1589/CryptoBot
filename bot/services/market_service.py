# bot/services/market_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Высокоуровневый сервис-фасад для агрегации рыночных данных
# от других специализированных сервисов.

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from bot.services.asic_service import AsicService
from bot.services.market_data_service import MarketDataService
from bot.utils.models import AsicMiner, MarketOverview


class MarketService:
    """
    Сервис-оркестратор, который объединяет данные из AsicService и
    MarketDataService для предоставления комплексных рыночных сводок.
    """

    def __init__(self, asic_service: AsicService, market_data_service: MarketDataService):
        """
        Инициализирует сервис с необходимыми зависимостями.

        :param asic_service: Сервис для получения данных по ASIC-майнерам.
        :param market_data_service: Сервис для получения общих рыночных данных.
        """
        self.asic_service = asic_service
        self.market_data_service = market_data_service
        logger.info("Сервис MarketService инициализирован.")

    async def get_market_overview(self, top_n_coins: int = 10) -> MarketOverview:
        """
        Асинхронно собирает и возвращает полную сводку по рынку,
        используя параллельные запросы к зависимым сервисам.

        :param top_n_coins: Количество топ-монет для включения в сводку.
        :return: Pydantic-модель MarketOverview с собранными данными.
        """
        logger.info("Запрос на получение полной сводки по рынку...")
        
        # Асинхронно и параллельно запрашиваем все необходимые данные
        results = await asyncio.gather(
            self.market_data_service.get_prices(['bitcoin']),
            self.market_data_service.get_top_coins_by_market_cap(limit=top_n_coins),
            self.market_data_service.get_btc_network_status(),
            self.market_data_service.get_halving_info(),
            return_exceptions=True
        )

        # Безопасно извлекаем результаты
        prices_result, top_coins_result, network_result, halving_result = results

        # Обрабатываем каждый результат, логируя ошибки, но не прерывая процесс
        btc_price = prices_result.get('bitcoin') if isinstance(prices_result, dict) else None
        if isinstance(prices_result, Exception):
            logger.error(f"Не удалось получить цену BTC: {prices_result}")

        top_coins = top_coins_result if isinstance(top_coins_result, list) else []
        if isinstance(top_coins_result, Exception):
            logger.error(f"Не удалось получить топ монет: {top_coins_result}")

        btc_network = network_result if not isinstance(network_result, Exception) else None
        if isinstance(network_result, Exception):
            logger.error(f"Не удалось получить статус сети BTC: {network_result}")

        halving = halving_result if not isinstance(halving_result, Exception) else None
        if isinstance(halving_result, Exception):
            logger.error(f"Не удалось получить информацию о халвинге: {halving_result}")

        overview = MarketOverview(
            btc_price_usd=btc_price,
            top_coins=top_coins,
            btc_network=btc_network,
            halving=halving,
        )
        
        logger.info("Сводка по рынку успешно сформирована.")
        return overview

    async def get_top_asics(
        self, electricity_cost: float, count: int = 20
    ) -> Tuple[List[AsicMiner], Optional[datetime]]:
        """
        Прокси-метод для получения топа ASIC-майнеров по прибыльности.
        Делегирует вызов напрямую в AsicService.

        :param electricity_cost: Стоимость электроэнергии в USD за кВт/ч.
        :param count: Количество ASIC для возврата.
        :return: Кортеж со списком моделей AsicMiner и временем последнего обновления.
        """
        try:
            return await self.asic_service.get_top_asics(electricity_cost, count=count)
        except Exception as e:
            logger.exception(f"Ошибка при получении топ ASIC: {e}")
            return [], None