import logging
import time
from bot.utils import dependencies
from bot.config.settings import settings

logger = logging.getLogger(__name__)

async def end_mining_session(user_id: int):
    """
    Завершает майнинг-сессию, рассчитывает чистый доход на основе фактического времени
    (за вычетом электричества) и начисляет его на баланс пользователя.
    """
    bot = dependencies.bot
    redis_client = dependencies.redis_client
    
    logger.info(f"Ending mining session for user {user_id}")

    session_data = await redis_client.hgetall(f"mining:session:{user_id}")
    if not session_data:
        logger.warning(f"No active mining session found for user {user_id} to end.")
        return

    # --- Получаем все необходимые данные для расчета ---

    # Тариф на электроэнергию
    user_tariff_name = await redis_client.get(f"user:{user_id}:tariff") or settings.DEFAULT_ELECTRICITY_TARIFF
    tariff_details = settings.ELECTRICITY_TARIFFS.get(user_tariff_name, {"cost_per_hour": 0.05})
    electricity_cost_per_second = tariff_details["cost_per_hour"] / 3600
    
    # Доходность оборудования
    profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))
    profit_per_second = profitability_per_day / (24 * 3600)

    # --- Вычисляем точное время работы ---
    start_time = int(session_data.get("start_time", int(time.time())))
    session_duration_real = int(time.time()) - start_time
    # Убеждаемся, что мы не насчитаем больше, чем за положенную длительность сессии
    actual_duration_seconds = min(session_duration_real, settings.MINING_DURATION_SECONDS)

    # --- Рассчитываем чистую прибыль ---
    gross_earned = actual_duration_seconds * profit_per_second
    total_electricity_cost = actual_duration_seconds * electricity_cost_per_second
    net_earned = max(0, gross_earned - total_electricity_cost)

    # Используем pipeline для атомарности операций: удаляем сессию и пополняем балансы
    async with redis_client.pipeline() as pipe:
        pipe.delete(f"mining:session:{user_id}")
        pipe.incrbyfloat(f"user:{user_id}:balance", net_earned)
        pipe.incrbyfloat(f"user:{user_id}:total_earned", net_earned)
        await pipe.execute()

    logger.info(f"User {user_id} finished session. Gross: {gross_earned:.4f}, Cost: {total_electricity_cost:.4f}, Net: {net_earned:.4f}.")

    # Отправляем пользователю подробное уведомление
    try:
        await bot.send_message(
            user_id,
            f"✅ Майнинг-сессия на <b>{session_data.get('asic_name')}</b> завершена!\n\n"
            f"📈 Грязный доход: <b>{gross_earned:.4f} монет</b>\n"
            f"⚡️ Расход на эл-во ({user_tariff_name}): <b>{total_electricity_cost:.4f} монет</b>\n\n"
            f"💰 Чистая прибыль зачислена на баланс: <b>{net_earned:.4f} монет</b>."
        )
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")