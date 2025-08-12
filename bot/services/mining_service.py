# ===============================================================
# Файл: bot/services/mining_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ)
# Описание: Сервис для выполнения расчетов доходности майнинга.
# ИСПРАВЛЕНИЕ: Исправлены вызовы методов MarketDataService для
#              соответствия новой архитектуре и устранения AttributeError.
# ===============================================================

import logging
import asyncio
import re
from typing import Optional

from bot.services.market_data_service import MarketDataService
from bot.utils.models import CalculationInput, CalculationResult

logger = logging.getLogger(__name__)

# --- Константы для расчетов ---
SECONDS_IN_DAY = 86400.0
BTC_BLOCK_TIME_SECONDS = 600.0
DAYS_IN_MONTH = 30.44
DAYS_IN_YEAR = 365.25

class MiningService:
    """
    Сервис, отвечающий за расчеты, связанные с майнингом.
    Возвращает структурированные данные, а не готовый текст.
    """
    def __init__(self, market_data_service: MarketDataService):
        self.market_data = market_data_service
        logger.info("MiningService initialized.")

    @staticmethod
    def _parse_hashrate_to_ths(hashrate_str: str) -> Optional[float]:
        """
        Парсит строку хешрейта (e.g., "110 TH/s", "9500 MH/s") в TH/s.
        """
        hashrate_str = hashrate_str.lower().replace(',', '.')
        match = re.search(r'([\d.]+)\s*(kh/s|mh/s|gh/s|th/s|ph/s|eh/s)', hashrate_str)
        if not match:
            return None
        
        value = float(match.group(1))
        unit = match.group(2)
        
        if unit == 'kh/s': return value / 1_000_000_000
        if unit == 'mh/s': return value / 1_000_000
        if unit == 'gh/s': return value / 1_000
        if unit == 'th/s': return value
        if unit == 'ph/s': return value * 1_000
        if unit == 'eh/s': return value * 1_000_000
            
        return None

    async def calculate_btc_profitability(
        self,
        calc_input: CalculationInput
    ) -> Optional[CalculationResult]:
        """
        Выполняет полный расчет доходности майнинга для Bitcoin (SHA-256).
        Возвращает Pydantic-модель с результатами или None в случае ошибки.
        """
        logger.info(f"Starting BTC calculation for input: {calc_input}")

        hashrate_ths = self._parse_hashrate_to_ths(calc_input.hashrate_str)
        if hashrate_ths is None:
            logger.error(f"Failed to parse hashrate string: {calc_input.hashrate_str}")
            return None

        # Шаг 1: Асинхронно получаем все необходимые рыночные данные
        # ИСПРАВЛЕНО: Вызываем новые, правильные методы
        results = await asyncio.gather(
            self.market_data.get_btc_price_usd(),
            self.market_data.get_network_hashrate_ths(),
            self.market_data.get_block_reward_btc(),
            return_exceptions=True
        )
        
        btc_price_usd, network_hashrate_ths, block_reward_btc = results
        usd_rub_rate = 95.0  # Заглушка, можно заменить на вызов API курса валют

        # Шаг 2: Валидация полученных данных
        required_data = [btc_price_usd, network_hashrate_ths, block_reward_btc]
        if any(isinstance(res, Exception) or res is None for res in required_data):
            logger.error(f"Failed to fetch market data for calculation. Results: {results}")
            return None

        # Шаг 3: Выполняем расчеты
        user_share = hashrate_ths / network_hashrate_ths
        blocks_per_day = SECONDS_IN_DAY / BTC_BLOCK_TIME_SECONDS
        
        gross_revenue_btc_daily = user_share * blocks_per_day * block_reward_btc
        gross_revenue_usd_daily = gross_revenue_btc_daily * btc_price_usd

        power_kwh_daily = (calc_input.power_consumption_watts / 1000.0) * 24.0
        electricity_cost_usd_daily = power_kwh_daily * calc_input.electricity_cost
        
        pool_fee_decimal = calc_input.pool_commission / 100.0
        pool_fee_usd_daily = gross_revenue_usd_daily * pool_fee_decimal
        
        total_expenses_usd_daily = electricity_cost_usd_daily + pool_fee_usd_daily
        net_profit_usd_daily = gross_revenue_usd_daily - total_expenses_usd_daily

        # Шаг 4: Собираем Pydantic-модель с результатами
        result_model = CalculationResult(
            btc_price_usd=btc_price_usd,
            usd_rub_rate=usd_rub_rate,
            network_hashrate_ths=network_hashrate_ths,
            block_reward_btc=block_reward_btc,
            gross_revenue_usd_daily=gross_revenue_usd_daily,
            electricity_cost_usd_daily=electricity_cost_usd_daily,
            pool_fee_usd_daily=pool_fee_usd_daily,
            total_expenses_usd_daily=total_expenses_usd_daily,
            net_profit_usd_daily=net_profit_usd_daily
        )
        
        logger.info(f"Calculation successful. Net profit: ${net_profit_usd_daily:.2f}/day.")
        return result_model