# =================================================================================
# Файл: bot/services/admin_service.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ИСПРАВЛЕНА)
# =================================================================================
import logging
import redis.asyncio as redis
from typing import Optional

from aiogram import Bot
from bot.config.settings import Settings # <<< ИСПРАВЛЕНО ЗДЕСЬ
from bot.services.mining_game_service import _KeyFactory as GameKeyFactory

logger = logging.getLogger(__name__)

class AdminService:
    """Сервис, инкапсулирующий все административные функции."""
    
    def __init__(self, redis_client: redis.Redis, settings: Settings, bot: Bot): # <<< ИСПРАВЛЕНО ЗДЕСЬ
        self.redis = redis_client
        self.settings = settings
        self.bot = bot
        self.admin_ids = settings.admin_ids_list # Используем правильное свойство
        self.game_keys = GameKeyFactory

    async def notify_admins(self, message: str, **kwargs):
        """Отправляет сообщение всем администраторам из конфига."""
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, message, **kwargs)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    async def get_global_stats(self) -> dict:
        """Собирает общую статистику по боту."""
        users_total = await self.redis.scard("users:all")
        users_active_day = await self.redis.scard("users:active:day")
        users_active_week = await self.redis.scard("users:active:week")
        return {
            "users_total": users_total,
            "users_active_day": users_active_day,
            "users_active_week": users_active_week,
        }

    async def get_game_stats(self) -> dict:
        """Получает глобальную статистику по игре 'Виртуальный Майнинг'."""
        stats_key = self.game_keys.global_stats()
        raw_stats = await self.redis.hgetall(stats_key)
        return {
            "active_sessions": int(raw_stats.get("active_sessions", 0)),
            "total_balance": float(raw_stats.get("total_balance", 0.0)),
            "pending_withdrawals": int(raw_stats.get("pending_withdrawals", 0)),
        }

    async def change_user_game_balance(self, user_id: int, amount: float) -> Optional[float]:
        """Изменяет игровой баланс пользователя на указанную сумму."""
        profile_key = self.game_keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            return None
        
        new_balance = await self.redis.hincrbyfloat(profile_key, "balance", amount)
        await self.redis.hincrbyfloat(self.game_keys.global_stats(), "total_balance", amount)
        
        logger.info(f"Admin changed game balance for user {user_id} by {amount}. New balance: {new_balance}")
        return new_balance