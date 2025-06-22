import logging
import time
from bot.utils import dependencies
from bot.config.settings import settings

logger = logging.getLogger(__name__)

async def end_mining_session(user_id: int):
    """
    Завершает майнинг-сессию, начисляет доход на постоянный баланс пользователя.
    """
    bot = dependencies.bot
    redis_client = dependencies.redis_client
    
    logger.info(f"Ending mining session for user {user_id}")

    session_data = await redis_client.hgetall(f"mining:session:{user_id}")
    if not session_data:
        logger.warning(f"No active mining session found for user {user_id} to end.")
        return

    # Расчет дохода за сессию
    profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))
    profit_per_second = profitability_per_day / (24 * 3600)
    session_duration = int(time.time()) - int(session_data.get("start_time", int(time.time())))
    
    # Ограничиваем длительность сессии максимальным значением, на случай сбоев
    actual_duration = min(session_duration, settings.MINING_DURATION_SECONDS)
    earned_amount = actual_duration * profit_per_second

    # Удаляем сессию и начисляем монеты на баланс
    # Используем pipeline для атомарности операций
    async with redis_client.pipeline() as pipe:
        pipe.delete(f"mining:session:{user_id}")
        pipe.incrbyfloat(f"user:{user_id}:balance", earned_amount)
        await pipe.execute()

    logger.info(f"User {user_id} finished session and earned {earned_amount:.4f} coins.")

    try:
        await bot.send_message(
            user_id,
            f"✅ Майнинг-сессия на <b>{session_data.get('asic_name')}</b> завершена!\n\n"
            f"💰 Ваш баланс пополнен на <b>{earned_amount:.4f} монет</b>.\n"
            f"Теперь вы можете вывести их в разделе 'Вывод средств'."
        )
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")