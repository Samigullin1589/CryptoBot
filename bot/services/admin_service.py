# ===============================================================
# Файл: bot/services/admin_service.py (ПРОДАКШН-ВЕРСИЯ АВГУСТ 2025)
# ===============================================================
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List

import redis.asyncio as redis
from aiogram.types import InlineKeyboardMarkup

# >>>>> НАЧАЛО ИСПРАВЛЕНИЯ: Добавлены импорты для синхронизации DI <<<<<
from aiogram import Bot
# Предполагается, что импорт Settings ведет сюда:
from bot.config.settings import Settings 
# >>>>> КОНЕЦ ИСПРАВЛЕНИЯ <<<<<

from bot.filters.access_filters import UserRole
from bot.keyboards.admin_keyboards import (
    get_admin_menu_keyboard, get_stats_menu_keyboard, 
    get_system_actions_keyboard, get_back_to_admin_menu_keyboard
)

logger = logging.getLogger(__name__)

class AdminService:
    """
    Сервис для сбора статистики и выполнения административных задач.
    Использует эффективные и безопасные методы работы с Redis.
    """
    
    # >>>>> НАЧАЛО ИСПРАВЛЕНИЯ: Обновленный конструктор <<<<<
    # Было: def __init__(self, redis_client: redis.Redis):
    def __init__(self, redis_client: redis.Redis, settings: Settings, bot: Bot):
        self.redis = redis_client
        self.settings = settings
        self.bot = bot
        self.admin_ids = settings.admin_ids_list
        self.game_keys = GameKeyFactory

    async def notify_admins(self, message: str, **kwargs):
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, message, **kwargs)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    async def get_global_stats(self) -> dict:
        users_total = await self.redis.scard("users:all")
        users_active_day = await self.redis.scard("users:active:day")
        users_active_week = await self.redis.scard("users:active:week")
        return {
            "users_total": users_total,
            "users_active_day": users_active_day,
            "users_active_week": users_active_week,
        }

    async def get_game_stats(self) -> dict:
        stats_key = self.game_keys.global_stats()
        raw_stats = await self.redis.hgetall(stats_key)
        return {
            "active_sessions": int(raw_stats.get("active_sessions", 0)),
            "total_balance": float(raw_stats.get("total_balance", 0.0)),
            "pending_withdrawals": int(raw_stats.get("pending_withdrawals", 0)),
        }

    async def change_user_game_balance(self, user_id: int, amount: float) -> float | None:
        profile_key = self.game_keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            return None
        
        new_balance = await self.redis.hincrbyfloat(profile_key, "balance", amount)
        await self.redis.hincrbyfloat(self.game_keys.global_stats(), "total_balance", amount)
        
        logger.info(f"Admin changed game balance for user {user_id} by {amount}. New balance: {new_balance}")
        return new_balance