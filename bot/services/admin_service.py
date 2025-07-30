# ===============================================================
# Файл: bot/services/admin_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ)
# Описание: Сервис для администрирования, с реализованной системой
# уведомлений и синхронизированный через единый KeyFactory.
# ===============================================================
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List

import redis.asyncio as redis
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import AdminConfig
from bot.utils.keys import KeyFactory
from bot.utils.models import UserRole
from bot.keyboards.admin_keyboards import (
    get_admin_menu_keyboard, get_stats_menu_keyboard,
    get_system_actions_keyboard, get_back_to_admin_menu_keyboard
)

logger = logging.getLogger(__name__)

class AdminService:
    """Сервис для сбора статистики и выполнения административных задач."""
    def __init__(self, bot: Bot, redis_client: redis.Redis, settings: AdminConfig):
        self.bot = bot
        self.redis = redis_client
        self.settings = settings
        self.keys = KeyFactory

    # --- Методы для отслеживания (вызываются извне) ---
    async def log_user_action(self, user_id: int, full_name: str, action: str):
        """Отслеживает действие пользователя (команда, кнопка)."""
        await self.redis.zincrby(self.keys.stats_actions_zset(), 1, action)
        logger.debug(f"User {full_name} ({user_id}) performed action: {action}")

    async def track_new_user(self, user_id: int):
        """Отмечает появление нового пользователя."""
        if await self.redis.sadd(self.keys.known_users_set(), user_id):
            timestamp = int(datetime.now(timezone.utc).timestamp())
            await self.redis.zadd(self.keys.user_first_seen_zset(), {str(user_id): timestamp})

    async def notify_admins(self, message: str):
        """Отправляет важное уведомление в главный чат администраторов."""
        try:
            await self.bot.send_message(
                self.settings.admin_chat_id,
                message,
                parse_mode="HTML"
            )
        except TelegramAPIError as e:
            logger.error(f"Не удалось отправить уведомление в чат администраторов ({self.settings.admin_chat_id}): {e}")

    # --- Методы для получения и форматирования статистики ---
    async def get_stats_page_content(self, stats_type: str) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает контент для указанной страницы статистики."""
        keyboard = get_back_to_admin_menu_keyboard()
        if stats_type == "general":
            stats = await self._get_general_stats()
            text = (f"<b>📊 Общая статистика</b>\n\n"
                    f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
                    f"🚀 Новых за 24 часа: <b>{stats['new_24h']}</b>\n"
                    f"🏃‍♂️ Активных за 24 часа: <b>{stats['active_24h']}</b>")
        elif stats_type == "mining":
            stats = await self._get_mining_stats()
            text = (f"<b>💎 Статистика 'Виртуального Майнинга'</b>\n\n"
                    f"⚡️ Активных сессий сейчас: <b>{stats.get('active_sessions', 0)}</b>\n"
                    f"💰 Всего монет на балансах: <b>{float(stats.get('total_balance', 0.0)):,.2f}</b>\n"
                    f"📤 Заявок на вывод: <b>{stats.get('pending_withdrawals', 0)}</b>")
        elif stats_type == "commands":
            top_commands = await self._get_command_stats()
            stats_text = "\n".join([f"🔹 <code>{cmd}</code> - {score} раз" for cmd, score in top_commands]) if top_commands else "Еще нет данных."
            text = f"<b>📈 Топ-10 действий</b>\n\n{stats_text}"
        else:
            raise KeyError(f"Unknown stats type: {stats_type}")
            
        return text, keyboard

    # --- Приватные методы для сбора данных ---
    async def _get_general_stats(self) -> Dict[str, Any]:
        one_day_ago = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
        async with self.redis.pipeline() as pipe:
            pipe.scard(self.keys.known_users_set())
            pipe.zcount(self.keys.user_last_activity_zset(), min=one_day_ago, max=-1)
            pipe.zcount(self.keys.user_first_seen_zset(), min=one_day_ago, max=-1)
            results = await pipe.execute()
        return {"total_users": results[0], "active_24h": results[1], "new_24h": results[2]}

    async def _get_mining_stats(self) -> Dict[str, Any]:
        return await self.redis.hgetall(self.keys.game_global_stats())

    async def _get_command_stats(self) -> List[Tuple[str, int]]:
        top_actions = await self.redis.zrevrange(self.keys.stats_actions_zset(), 0, 9, withscores=True)
        return [(cmd, int(score)) for cmd, score in top_actions]

    # --- Системные действия ---
    async def clear_asic_cache(self) -> int:
        keys_to_delete = [self.keys.asics_last_update(), self.keys.asics_sorted_set()]
        async for key in self.redis.scan_iter(f"asic:*"):
            keys_to_delete.append(key)
        return await self.redis.delete(*keys_to_delete) if keys_to_delete else 0

    # --- Методы для навигации в админ-панели ---
    async def get_main_menu_content(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        user_role = UserRole.USER
        if user_id in self.settings.super_admin_ids:
            user_role = UserRole.SUPER_ADMIN
        elif user_id in self.settings.admin_ids:
            user_role = UserRole.ADMIN
        
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard

    async def get_stats_menu_content(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = "<b>📊 Статистика</b>\n\nВыберите интересующий вас отчет:"
        keyboard = get_stats_menu_keyboard()
        return text, keyboard

    async def get_system_menu_content(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = "<b>⚙️ Системные действия</b>\n\n<b>Внимание:</b> эти действия могут повлиять на работу бота."
        keyboard = get_system_actions_keyboard()
        return text, keyboard