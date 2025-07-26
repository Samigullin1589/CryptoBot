# ===============================================================
# Файл: bot/services/mining_service.py (Альфа-версия)
# Описание: Сервис для выполнения расчетов доходности майнинга.
# Реализована корректная математика для чисел с плавающей
# запятой и улучшенное форматирование вывода.
# ===============================================================

import logging
import asyncio
from textwrap import dedent

from bot.services.market_data_service import MarketDataService

# Настройка логирования
log = logging.getLogger(__name__)

# --- Константы для расчетов ---
SECONDS_IN_DAY = 86400.0
# Среднее время блока Bitcoin в секундах
BTC_BLOCK_TIME_SECONDS = 600.0 
# Среднее количество дней в месяце и году
DAYS_IN_MONTH = 30.44
DAYS_IN_YEAR = 365.25


class MiningService:
    """
    Сервис, отвечающий за расчеты, связанные с майнингом.
    """

    def __init__(self, market_data_service: MarketDataService):
        """
        Инициализация сервиса.
        :param market_data_service: Экземпляр сервиса для получения рыночных данных.
        """
        self.market_data = market_data_service
        log.info("MiningService инициализирован.")

    async def calculate(
        self,
        hashrate_ths: float,
        power_consumption_watts: int,
        electricity_cost: float,
        pool_commission: float
    ) -> str:
        """
        Выполняет полный расчет доходности майнинга.

        :param hashrate_ths: Хешрейт оборудования в TH/s.
        :param power_consumption_watts: Потребляемая мощность в Ваттах.
        :param electricity_cost: Стоимость электроэнергии в USD за кВт/ч.
        :param pool_commission: Комиссия пула в процентах.
        :return: Отформатированная строка с результатами расчета.
        """
        log.info(
            f"Запуск расчета для {hashrate_ths} TH/s, {power_consumption_watts}W, "
            f"э/э: ${electricity_cost}/kWh, комиссия пула: {pool_commission}%"
        )

        # Шаг 1: Асинхронно получаем все необходимые данные от market_data_service
        results = await asyncio.gather(
            self.market_data.get_btc_price_usd(),
            self.market_data.get_network_hashrate_ths(),
            self.market_data.get_block_reward_btc(),
            self.market_data.get_usd_rub_rate(),
            return_exceptions=True
        )

        # Распаковываем результаты
        btc_price_usd, network_hashrate_ths, block_reward_btc, usd_rub_rate = results

        # Шаг 2: Проверяем, все ли данные были успешно получены
        missing_data = []
        if isinstance(btc_price_usd, Exception) or not btc_price_usd:
            missing_data.append("цену BTC")
            log.error(f"Ошибка получения цены BTC: {btc_price_usd}")
        if isinstance(network_hashrate_ths, Exception) or not network_hashrate_ths:
            missing_data.append("хешрейт сети")
            log.error(f"Ошибка получения хешрейта сети: {network_hashrate_ths}")
        if isinstance(block_reward_btc, Exception) or not block_reward_btc:
            missing_data.append("награду за блок")
            log.error(f"Ошибка получения награды за блок: {block_reward_btc}")

        if missing_data:
            error_message = f"Не удалось получить ключевые данные для расчета: {', '.join(missing_data)}. Попробуйте позже."
            log.error(f"Расчет прерван из-за отсутствия данных: {missing_data}")
            return f"❌ <b>Ошибка:</b> {error_message}"

        # Шаг 3: Выполняем расчеты
        # 3.1 Расчет "грязного" дохода
        user_share_of_network = float(hashrate_ths) / float(network_hashrate_ths)
        blocks_found_per_day = SECONDS_IN_DAY / BTC_BLOCK_TIME_SECONDS
        gross_revenue_btc_daily = user_share_of_network * blocks_found_per_day * float(block_reward_btc)
        gross_revenue_usd_daily = gross_revenue_btc_daily * float(btc_price_usd)

        # 3.2 Расчет расходов
        power_kwh_daily = (float(power_consumption_watts) / 1000.0) * 24.0
        electricity_cost_usd_daily = power_kwh_daily * float(electricity_cost)
        pool_fee_decimal = float(pool_commission) / 100.0
        pool_fee_usd_daily = gross_revenue_usd_daily * pool_fee_decimal
        total_expenses_usd_daily = electricity_cost_usd_daily + pool_fee_usd_daily

        # 3.3 Расчет чистой прибыли
        net_profit_usd_daily = gross_revenue_usd_daily - total_expenses_usd_daily

        # Шаг 4: Форматируем итоговый текст
        result_text = dedent(f"""
            📊 <b>Результаты расчета доходности</b>

            <b>Исходные данные:</b>
            - Цена BTC: <code>${btc_price_usd:,.2f}</code>
            - Курс USD/RUB: <code>{usd_rub_rate:,.2f} ₽</code>
            - Хешрейт сети: <code>{network_hashrate_ths / 1_000_000:,.2f} EH/s</code>
            - Награда за блок: <code>{block_reward_btc:.4f} BTC</code>

            ---

            <b>💰 Доходы (грязными):</b>
            - В день: <code>${gross_revenue_usd_daily:.2f}</code> / <code>{gross_revenue_usd_daily * usd_rub_rate:.2f} ₽</code>
            - В месяц: <code>${gross_revenue_usd_daily * DAYS_IN_MONTH:.2f}</code> / <code>{gross_revenue_usd_daily * DAYS_IN_MONTH * usd_rub_rate:.2f} ₽</code>

            <b>🔌 Расходы:</b>
            - Электричество/день: <code>${electricity_cost_usd_daily:.2f}</code>
            - Комиссия пула ({pool_commission}%)/день: <code>${pool_fee_usd_daily:.2f}</code>
            - <b>Всего расходов/день:</b> <code>${total_expenses_usd_daily:.2f}</code>

            ---

            ✅ <b>Чистая прибыль:</b>
            - <b>В день:</b> <code>${net_profit_usd_daily:.2f}</code> / <code>{net_profit_usd_daily * usd_rub_rate:.2f} ₽</code>
            - <b>В месяц:</b> <code>${net_profit_usd_daily * DAYS_IN_MONTH:.2f}</code> / <code>{net_profit_usd_daily * DAYS_IN_MONTH * usd_rub_rate:.2f} ₽</code>
            - <b>В год:</b> <code>${net_profit_usd_daily * DAYS_IN_YEAR:.2f}</code> / <code>{net_profit_usd_daily * DAYS_IN_YEAR * usd_rub_rate:.2f} ₽</code>
        """)

        if net_profit_usd_daily < 0:
            result_text += "\n\n⚠️ <b>Внимание:</b> при текущих параметрах майнинг невыгоден."

        log.info(f"Расчет успешно завершен. Чистая прибыль: ${net_profit_usd_daily:.2f}/день.")
        return result_text.strip()
