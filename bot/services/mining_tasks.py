import logging
import redis.asyncio as redis
from aiogram import Bot

from bot.config.settings import settings

logger = logging.getLogger(__name__)

async def end_mining_session(user_id: int, bot: Bot, redis_client: redis.Redis):
    logger.info(f"Ending mining session for user {user_id}")

    total_reward = (settings.MINING_RATE_PER_HOUR / 3600) * settings.MINING_DURATION_SECONDS

    async with redis_client.pipeline() as pipe:
        pipe.delete(f"mining:session:{user_id}")
        pipe.set(f"mining:claimable:{user_id}", total_reward)
        await pipe.execute()

    try:
        await bot.send_message(
            user_id,
            f"Майнинг завершен! 🎉\n\nВы можете забрать свою награду "
            f"({total_reward:.2f} монет) с помощью команды /claim_rewards."
        )
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")