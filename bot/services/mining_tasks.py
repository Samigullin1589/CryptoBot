import logging
import time
from bot.utils import dependencies
from bot.config.settings import settings

logger = logging.getLogger(__name__)

async def end_mining_session(user_id: int):
    """
    Завершает майнинг-сессию, рассчитывает чистый доход (за вычетом электричества) 
    и начисляет его на баланс пользователя.
    """
    bot = dependencies.bot
    redis_client = dependencies.redis_client
    
    logger.info(f"Ending mining session for user {user_id}")

    session_data = await redis_client.hgetall(f"mining:session:{user_id}")
    if not session_data:
        logger.warning(f"No active mining session found for user {user_id} to end.")
        return

    # Получаем текущий тариф пользователя
    user_tariff_name = await redis_client.get(f"user:{user_id}:tariff")
    if not user_tariff_name:
        user_tariff_name = settings.DEFAULT_ELECTRICITY_TARIFF
    
    # Получаем стоимость тарифа в час
    electricity_cost_per_hour = settings.ELECTRICITY_TARIFFS.get(user_tariff_name, 0.05)
    
    # Расчет "грязного" дохода
    profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))
    profit_per_hour = profitability_per_day / 24
    session_duration_hours = settings.MINING_DURATION_SECONDS / 3600
    gross_earned = session_duration_hours * profit_per_hour
    
    # Расчет расходов на электричество
    total_electricity_cost = session_duration_hours * electricity_cost_per_hour
    
    # Расчет чистой прибыли
    net_earned = gross_earned - total_electricity_cost

    # Не даем балансу уйти в минус, если тариф дороже дохода
    net_earned = max(0, net_earned)

    async with redis_client.pipeline() as pipe:
        pipe.delete(f"mining:session:{user_id}")
        pipe.incrbyfloat(f"user:{user_id}:balance", net_earned)
        pipe.incrbyfloat(f"user:{user_id}:total_earned", net_earned)
        await pipe.execute()

    logger.info(f"User {user_id} finished session. Gross: {gross_earned:.4f}, Cost: {total_electricity_cost:.4f}, Net: {net_earned:.4f}.")

    try:
        await bot.send_message(
            user_id,
            f"✅ Майнинг-сессия на <b>{session_data.get('asic_name')}</b> завершена!\n\n"
            f"📈 Грязный доход: <b>{gross_earned:.4f} монет</b>\n"
            f"⚡️ Расход на эл-во: <b>{total_electricity_cost:.4f} монет</b>\n"
            f"💰 Чистая прибыль зачислена на баланс: <b>{net_earned:.4f} монет</b>."
        )
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")