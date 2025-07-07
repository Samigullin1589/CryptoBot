import logging
from datetime import datetime, timedelta
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class AdminService:
    """
    Сервис для сбора и обработки статистики для панели администратора.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def get_general_stats(self) -> dict:
        """Собирает общую статистику по пользователям."""
        total_users = await self.redis.scard("users:known")
        
        one_day_ago_ts = int((datetime.now() - timedelta(days=1)).timestamp())
        
        active_24h = await self.redis.zcount("stats:user_activity", min=one_day_ago_ts, max=-1)
        new_24h = await self.redis.zcount("stats:user_first_seen", min=one_day_ago_ts, max=-1)

        return {
            "total_users": total_users,
            "active_24h": active_24h,
            "new_24h": new_24h
        }

    async def get_mining_stats(self) -> dict:
        """Собирает статистику по модулю 'Виртуальный Майнинг'."""
        active_sessions = len(await self.redis.keys("mining:session:*"))
        
        total_balance_keys = await self.redis.keys("user:*:balance")
        total_withdrawn_keys = await self.redis.keys("user:*:total_withdrawn")
        
        total_balance = 0
        if total_balance_keys:
            balance_values = await self.redis.mget(total_balance_keys)
            total_balance = sum([float(v) for v in balance_values if v is not None])

        total_withdrawn = 0
        if total_withdrawn_keys:
            withdrawn_values = await self.redis.mget(total_withdrawn_keys)
            total_withdrawn = sum([float(v) for v in withdrawn_values if v is not None])
        
        total_referrals = await self.redis.scard("referred_users")

        return {
            "active_sessions": active_sessions,
            "total_balance": total_balance,
            "total_withdrawn": total_withdrawn,
            "total_referrals": total_referrals,
        }

    async def get_command_stats(self) -> list:
        """Получает топ-10 самых используемых команд."""
        top_commands = await self.redis.zrevrange("stats:commands", 0, 9, withscores=True)
        return [(cmd.decode('utf-8'), int(score)) for cmd, score in top_commands]