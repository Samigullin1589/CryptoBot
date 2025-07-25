# ===============================================================
# Файл: bot/services/mining_service.py (АЛЬФА-РЕШЕНИЕ)
# Описание: Метод calculate оптимизирован с использованием
# Blockchain.com как основного источника данных.
# ===============================================================

import logging
from bot.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

class MiningService:
    def __init__(self, market_data_service: MarketDataService):
        self.market_data_service = market_data_service

    async def calculate(
        self, 
        hashrate_ths: float, 
        power_consumption_watts: int, 
        electricity_cost: float,
        pool_commission: float,
        coin_symbol: str = "BTC",
        force_refresh: bool = True
    ) -> str:
        """
        Производит расчет доходности, используя все параметры, включая комиссию пула.
        force_refresh: принудительно обновляет данные сети, игнорируя кэш.
        """
        logger.info(
            f"Calculating for {hashrate_ths} TH/s, {power_consumption_watts}W, "
            f"coin: {coin_symbol}, electricity_cost: ${electricity_cost}/kWh, pool_fee: {pool_commission}%, "
            f"force_refresh={force_refresh}"
        )

        # Валидация входных данных
        if hashrate_ths <= 0 or power_consumption_watts <= 0 or electricity_cost < 0 or pool_commission < 0:
            return "❌ Неверные входные данные для расчета. Проверьте параметры (hashrate, мощность, стоимость электроэнергии и комиссию пула должны быть положительными)."

        # Получение данных сети с принудительным обновлением
        network_data = await self.market_data_service.get_coin_network_data(coin_symbol, force_refresh)
        if not network_data:
            return "❌ Не удалось получить данные о сети для расчета. Попробуйте позже или проверьте подключение к API."

        coin_price_usd = network_data.get("price", 0.0)
        network_hashrate_ths = network_data.get("network_hashrate", 0.0)
        block_reward_coins = network_data.get("block_reward", 0.0)
        
        if network_hashrate_ths <= 0 or coin_price_usd <= 0 or block_reward_coins <= 0:
            logger.error(
                f"Received zero or invalid values from API for {coin_symbol}. "
                f"Hashrate: {network_hashrate_ths} TH/s, Price: ${coin_price_usd}, Block Reward: {block_reward_coins} BTC"
            )
            return "❌ Получены неверные данные от API (цена, хешрейт или награда за блок равны нулю или некорректны). Расчет невозможен."

        # Расчет доли пользователя в сети
        user_share = hashrate_ths / network_hashrate_ths
        blocks_per_day = (60 / 10) * 24  # Предполагаем среднее время блока 10 минут для BTC
        coins_per_day = user_share * block_reward_coins * blocks_per_day
        gross_income_usd_day = coins_per_day * coin_price_usd
        
        # Расчет расходов на электроэнергию
        power_consumption_kwh_day = (power_consumption_watts * 24) / 1000
        electricity_cost_day = power_consumption_kwh_day * electricity_cost
        
        # Расчет комиссии пула
        pool_fee_usd_day = gross_income_usd_day * (pool_commission / 100)
        net_profit_usd_day = gross_income_usd_day - electricity_cost_day - pool_fee_usd_day
        
        net_profit_usd_month = net_profit_usd_day * 30

        # Форматирование ответа
        response_message = (
            f"<b>📊 Результаты расчета для {hashrate_ths} TH/s ({power_consumption_watts} Вт):</b>\n\n"
            f"<b>Доход (грязными):</b>\n"
            f"  - В день: <b>${gross_income_usd_day:.2f}</b>\n"
            f"  - В месяц: <b>${gross_income_usd_day * 30:.2f}</b>\n\n"
            f"<b>Расходы:</b>\n"
            f"  - Электричество: <b>${electricity_cost_day:.2f}/день</b> (при ${electricity_cost:.4f}/кВтч)\n"
            f"  - Комиссия пула: <b>${pool_fee_usd_day:.2f}/день</b> ({pool_commission}%)\n\n"
            f"<b>✅ Чистая прибыль:</b>\n"
            f"  - В день: <b>${net_profit_usd_day:.2f}</b>\n"
            f"  - В месяц: <b>${net_profit_usd_month:.2f}</b>\n\n"
            f"<pre>Расчет основан на текущих данных:\n"
            f"Цена {coin_symbol}: ${coin_price_usd:,.2f}\n"
            f"Хешрейт сети: {network_hashrate_ths:,.4f} TH/s\n"
            f"Награда за блок: {block_reward_coins:.8f} {coin_symbol}</pre>"
        )
        
        return response_message