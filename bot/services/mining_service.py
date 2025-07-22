# ===============================================================
# Файл: bot/services/mining_service.py (АЛЬФА-ВЕРСИЯ)
# Описание: Метод calculate теперь принимает точное энергопотребление.
# ===============================================================
import logging
from bot.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

class MiningService:
    def __init__(self, market_data_service: MarketDataService):
        self.market_data_service = market_data_service

    # --- ИЗМЕНЕНО: Метод теперь принимает hashrate и power_consumption ---
    async def calculate(
        self, 
        hashrate_ths: float, 
        power_consumption_watts: int, 
        electricity_cost: float, 
        coin_symbol: str = "BTC"
    ) -> str:
        """
        Производит расчет доходности, используя актуальные данные о сети, цене монеты
        и точные характеристики оборудования.
        """
        logger.info(
            f"Calculating for {hashrate_ths} TH/s, {power_consumption_watts}W, "
            f"coin: {coin_symbol}, electricity_cost: ${electricity_cost}/kWh"
        )

        # 1. Получаем актуальные данные о сети
        network_data = await self.market_data_service.get_coin_network_data(coin_symbol)
        
        if not network_data:
            return "❌ Не удалось получить данные о сети для расчета. Попробуйте позже."

        # Извлекаем данные
        coin_price_usd = network_data["price"]
        network_hashrate_ths = network_data["network_hashrate"] / 1_000_000_000_000
        block_reward_coins = network_data["block_reward"]
        
        if network_hashrate_ths == 0 or coin_price_usd == 0:
            logger.error(f"Received zero values from API for {coin_symbol}. Hashrate: {network_hashrate_ths}, Price: {coin_price_usd}")
            return "❌ Получены неверные данные от API (цена или хешрейт равны нулю). Расчет невозможен."

        # 2. Расчеты
        user_share = hashrate_ths / network_hashrate_ths
        blocks_per_day = (60 / 10) * 24
        coins_per_day = user_share * block_reward_coins * blocks_per_day
        gross_income_usd_day = coins_per_day * coin_price_usd
        
        # Расходы на электричество на основе точного потребления
        power_consumption_kwh_day = (power_consumption_watts * 24) / 1000
        electricity_cost_day = power_consumption_kwh_day * electricity_cost
        
        net_profit_usd_day = gross_income_usd_day - electricity_cost_day
        net_profit_usd_month = net_profit_usd_day * 30

        # 3. Формируем красивый ответ
        response_message = (
            f"<b>📊 Результаты расчета для {hashrate_ths} TH/s ({power_consumption_watts} Вт):</b>\n\n"
            f"<b>Доход (грязными):</b>\n"
            f"  - В день: <b>${gross_income_usd_day:.2f}</b>\n"
            f"  - В месяц: <b>${gross_income_usd_day * 30:.2f}</b>\n\n"
            f"<b>Расходы на электричество (при ${electricity_cost}/кВтч):</b>\n"
            f"  - В день: <b>${electricity_cost_day:.2f}</b>\n"
            f"  - В месяц: <b>${electricity_cost_day * 30:.2f}</b>\n\n"
            f"<b>✅ Чистая прибыль:</b>\n"
            f"  - В день: <b>${net_profit_usd_day:.2f}</b>\n"
            f"  - В месяц: <b>${net_profit_usd_month:.2f}</b>\n\n"
            f"<pre>Расчет основан на текущих данных:\n"
            f"Цена {coin_symbol}: ${coin_price_usd:,.2f}\n"
            f"Хешрейт сети: {network_hashrate_ths:,.0f} TH/s</pre>"
        )
        
        return response_message
