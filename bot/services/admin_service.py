# ===============================================================
# Файл: bot/services/admin_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОБЪЕДИНЕННАЯ)
# Описание: Единый сервис для всей логики администрирования.
# ИСПРАВЛЕНИЕ: Объединены функции из двух версий файла,
# добавлена недостающая функция track_action и исправлена работа с DI.
# ===============================================================
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List

import redis.asyncio as redis
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import Settings
from bot.filters.access_filters import UserRole
from bot.keyboards.admin_keyboards import (
    get_admin_menu_keyboard, get_stats_menu_keyboard,
    get_system_actions_keyboard, get_back_to_admin_menu_keyboard
)
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class AdminService:
    """
    Сервис для сбора статистики и выполнения административных задач.
    Использует эффективные и безопасные методы работы с Redis.
    """
    def __init__(self, redis: redis.Redis, settings: Settings, bot: Bot):
        self.redis = redis
        self.settings = settings
        self.bot = bot
        self.admin_ids: List[int] = settings.admin_ids
        self.keys = KeyFactory

    # --- Методы для отслеживания статистики (ВОССТАНОВЛЕНО) ---
    async def track_action(self, user_id: int, action_name: str):
        """Отслеживает использование команды или нажатие на кнопку."""
        await self.redis.zincrby("stats:actions", 1, action_name)
        
    # --- Уведомления ---
    async def notify_admins(self, message: str, **kwargs):
        """Отправляет уведомление всем администраторам из списка."""
        if not self.admin_ids:
            logger.warning("Попытка отправить уведомление, но список ID администраторов пуст.")
            return
            
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, message, **kwargs)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    # --- Получение статистики ---
    async def get_global_stats(self) -> dict:
        """Собирает общую статистику по пользователям."""
        users_total = await self.redis.scard(self.keys.all_users_set())
        
        now = datetime.utcnow()
        today_str = now.strftime('%Y-%m-%d')
        week_str = now.strftime('%Y-%U')
        day_key = f"users:active:day:{today_str}"
        week_key = f"users:active:week:{week_str}"
        
        users_active_day = await self.redis.scard(day_key)
        users_active_week = await self.redis.scard(week_key)
        return {
            "users_total": users_total,
            "users_active_day": users_active_day,
            "users_active_week": users_active_week,
        }

    async def get_game_stats(self) -> dict:
        """Собирает статистику по игровому модулю."""
        stats_key = self.keys.game_stats()
        raw_stats = await self.redis.hgetall(stats_key)
        return {
            "active_sessions": int(raw_stats.get("active_sessions", 0)),
            "total_balance": float(raw_stats.get("total_balance", 0.0)),
            "pending_withdrawals": int(raw_stats.get("pending_withdrawals", 0)),
        }

    # --- Управление игрой ---
    async def change_user_game_balance(self, user_id: int, amount: float) -> float | None:
        """Изменяет игровой баланс пользователя."""
        profile_key = self.keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            return None
        
        new_balance = await self.redis.hincrbyfloat(profile_key, "balance", amount)
        await self.redis.hincrbyfloat(self.keys.game_stats(), "total_balance", amount)
        
        logger.info(f"Admin changed game balance for user {user_id} by {amount}. New balance: {new_balance}")
        return new_balance
        
    # --- Системные действия ---
    async def clear_asic_cache(self) -> int:
        keys_to_delete = []
        async for key in self.redis.scan_iter(f"{self.keys.asic_hash('')}*"):
            keys_to_delete.append(key)
        
        if not keys_to_delete:
            return 0
            
        return await self.redis.delete(*keys_to_delete)

    # --- Навигация в админ-панели ---
    async def get_main_menu_content(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        # В будущем здесь можно будет получать роль из UserService
        user_role = UserRole.SUPER_ADMIN if user_id in self.settings.admin_ids else UserRole.ADMIN
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard