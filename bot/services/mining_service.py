# bot/services/mining_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис, отвечающий за выполнение расчетов доходности майнинга
# на основе актуальных рыночных данных.

import asyncio
import re
from typing import Optional

from loguru import logger

from bot.services.market_data_service import MarketDataService
from bot.utils.models import CalculationInput, CalculationResult

# --- Физические и экономические константы ---
SECONDS_IN_DAY = 86400.0


class MiningService:
    """
    Выполняет сложные расчеты доходности майнинга, абстрагируя математику
    от остальной части приложения. Возвращает структурированные данные,
    а не готовый для отправки пользователю текст.
    """

    def __init__(self, market_data_service: MarketDataService):
        """
        Инициализирует сервис с зависимостью от MarketDataService.

        :param market_data_service: Сервис для получения актуальных рыночных данных.
        """
        self.market_data = market_data_service
        logger.info("Сервис MiningService инициализирован.")

    @staticmethod
    def _parse_hashrate_to_ths(hashrate_str: str) -> Optional[float]:
        """
        Парсит строку с хешрейтом (например, "110 TH/s", "9500 MH/s")
        и конвертирует её в значение в TH/s (Терахеш в секунду).

        :param hashrate_str: Входная строка.
        :return: Хешрейт в TH/s или None, если парсинг не удался.
        """
        try:
            # Нормализация строки: нижний регистр, замена запятой на точку
            normalized_str = hashrate_str.lower().replace(',', '.')
            match = re.search(r'([\d.]+)\s*(kh/s|mh/s|gh/s|th/s|ph/s|eh/s)', normalized_str)
            
            if not match:
                return None
            
            value = float(match.group(1))
            unit = match.group(2)
            
            # Коэффициенты для перевода в TH/s
            multipliers = {
                'kh/s': 1e-9,
                'mh/s': 1e-6,
                'gh/s': 1e-3,
                'th/s': 1.0,
                'ph/s': 1e3,
                'eh/s': 1e6,
            }
            return value * multipliers.get(unit, 0.0)
        except (ValueError, TypeError):
            logger.warning(f"Не удалось распознать хешрейт: '{hashrate_str}'")
            return None

    async def calculate_btc_profitability(
        self,
        calc_input: CalculationInput
    ) -> Optional[CalculationResult]:
        """
        Выполняет полный расчет доходности майнинга для Bitcoin (алгоритм SHA-256).
        Асинхронно собирает все необходимые данные и возвращает Pydantic-модель
        с результатами или None в случае ошибки.
        """
        logger.info(f"Начинаю расчет доходности BTC для: {calc_input}")

        hashrate_ths = self._parse_hashrate_to_ths(calc_input.hashrate_str)
        if hashrate_ths is None:
            logger.error(f"Некорректный формат хешрейта: {calc_input.hashrate_str}")
            return None

        # Шаг 1: Асинхронно и параллельно получаем все необходимые рыночные данные
        results = await asyncio.gather(
            self.market_data.get_prices(['bitcoin']),
            self.market_data.get_network_hashrate_ths(),
            self.market_data.get_block_reward_btc(),
            self.market_data.get_usd_rub_rate(),
            return_exceptions=True
        )
        
        # Шаг 2: Безопасно извлекаем и валидируем полученные данные
        prices, network_hashrate_ths, block_reward_btc, usd_rub_rate = results
        btc_price_usd = prices.get('bitcoin') if isinstance(prices, dict) else None

        required_data = {
            "Цена BTC": btc_price_usd,
            "Хешрейт сети": network_hashrate_ths,
            "Награда за блок": block_reward_btc,
            "Курс USD/RUB": usd_rub_rate,
        }

        for name, value in required_data.items():
            if isinstance(value, Exception) or value is None:
                logger.error(f"Не удалось получить данные для расчета: '{name}'. Ошибка: {value}")
                return None

        # Шаг 3: Выполняем расчеты
        user_share = hashrate_ths / network_hashrate_ths
        blocks_per_day = SECONDS_IN_DAY / self.market_data.config.AVG_BLOCK_TIME_MINUTES / 60
        
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
        
        logger.info(f"Расчет успешно завершен. Чистая прибыль: ${net_profit_usd_daily:.2f}/день.")
        return result_model