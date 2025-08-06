# ===============================================================
# Файл: bot/services/admin_service.py (ПРОДАКШН-ВЕРСИЯ - ФИНАЛЬНАЯ)
# Описание: Сервис для сбора статистики и выполнения административных задач.
# ИСПРАВЛЕНИЕ: Конструктор приведен в полное соответствие с DI-контейнером.
# ===============================================================
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List

import redis.asyncio as redis
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

# ИСПРАВЛЕНО: Добавлены все необходимые импорты
from bot.config.settings import Settings 
from bot.utils.keys import KeyFactory
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
    
    # ИСПРАВЛЕНО: Конструктор полностью синхронизирован с dependencies.py
    def __init__(self, redis: redis.Redis, settings: Settings, bot: Bot):
        """
        Инициализирует сервис администратора.

        :param redis: Асинхронный клиент Redis.
        :param settings: Глобальные настройки бота.
        :param bot: Экземпляр бота для отправки сообщений.
        """
        self.redis = redis
        self.settings = settings
        self.bot = bot
        # ИСПРАВЛЕНО: Используется корректное имя поля из настроек
        self.admin_ids = settings.ADMIN_USER_IDS
        # ИСПРАВЛЕНО: Используется корректное имя фабрики ключей
        self.keys = KeyFactory

    async def notify_admins(self, message: str, **kwargs):
        """Отправляет уведомление всем администраторам из списка."""
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, message, **kwargs)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    async def get_global_stats(self) -> dict:
        """Собирает общую статистику по пользователям."""
        # Эти ключи должны быть определены в вашем middleware
        users_total = await self.redis.scard("users:all")
        users_active_day = await self.redis.scard("users:active:day")
        users_active_week = await self.redis.scard("users:active:week")
        return {
            "users_total": users_total,
            "users_active_day": users_active_day,
            "users_active_week": users_active_week,
        }

    async def get_game_stats(self) -> dict:
        """Собирает статистику по игровому модулю."""
        # Предполагаем, что у KeyFactory есть метод для игровых ключей
        stats_key = self.keys.game_stats() 
        raw_stats = await self.redis.hgetall(stats_key)
        return {
            "active_sessions": int(raw_stats.get("active_sessions", 0)),
            "total_balance": float(raw_stats.get("total_balance", 0.0)),
            "pending_withdrawals": int(raw_stats.get("pending_withdrawals", 0)),
        }

    async def change_user_game_balance(self, user_id: int, amount: float) -> float | None:
        """Изменяет игровой баланс пользователя."""
        profile_key = self.keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            return None
        
        new_balance = await self.redis.hincrbyfloat(profile_key, "balance", amount)
        await self.redis.hincrbyfloat(self.keys.game_stats(), "total_balance", amount)
        
        logger.info(f"Admin changed game balance for user {user_id} by {amount}. New balance: {new_balance}")
        return new_balance

