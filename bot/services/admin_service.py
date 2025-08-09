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
from bot.utils.models import UserRole # <-- ИСПРАВЛЕНО
from bot.keyboards.admin_keyboards import (
    get_admin_menu_keyboard, get_stats_menu_keyboard,
    get_system_actions_keyboard, get_back_to_admin_menu_keyboard
)
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class AdminService:
    """
    Сервис для сбора статистики и выполнения административных задач.
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
        """Отправляет уведомление всем администраторам."""
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, message, **kwargs)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

    # --- Методы для получения и форматирования страниц статистики ---
    async def get_stats_page_content(self, stats_type: str) -> Tuple[str, InlineKeyboardMarkup]:
        if stats_type == "general":
            stats = await self.get_global_stats()
            text = (
                "<b>📊 Общая статистика</b>\n\n"
                f"👥 Всего пользователей: <b>{stats['users_total']}</b>\n"
                f"☀️ Активных за день: <b>{stats['users_active_day']}</b>\n"
                f"📅 Активных за неделю: <b>{stats['users_active_week']}</b>"
            )
        # Другие типы статистики можно добавить здесь
        else:
            raise KeyError(f"Unknown stats type: {stats_type}")
        
        return text, get_back_to_admin_menu_keyboard()

    # --- Приватные методы сбора данных ---
    async def get_global_stats(self) -> dict:
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

    # --- Навигация в админ-панели ---
    async def get_main_menu_content(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        user_role = UserRole.SUPER_ADMIN if user_id in self.settings.admin_ids else UserRole.ADMIN
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard