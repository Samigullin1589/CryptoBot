# ===============================================================
# Файл: bot/services/admin_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ РЕАЛИЗАЦИЯ)
# Описание: Единый сервис для всей логики администрирования.
# ИСПРАВЛЕНИЕ: Реализованы недостающие методы для сбора игровой
#              статистики и статистики по командам.
# ===============================================================
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

import redis.asyncio as redis
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import Settings
from bot.utils.models import UserRole
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

    # --- Методы для отслеживания статистики ---
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
        """
        Возвращает контент для страницы статистики в зависимости от типа.
        """
        if stats_type == "general":
            stats = await self.get_global_stats()
            text = (
                "<b>📊 Общая статистика</b>\n\n"
                f"👥 Всего пользователей: <b>{stats['users_total']}</b>\n"
                f"☀️ Активных за день: <b>{stats['users_active_day']}</b>\n"
                f"📅 Активных за неделю: <b>{stats['users_active_week']}</b>"
            )
        elif stats_type == "mining":
            stats = await self.get_game_stats()
            text = (
                "<b>🎮 Игровая статистика</b>\n\n"
                f"🕹 Активных сессий: <b>{stats.get('active_sessions', 0)}</b>\n"
                f"💰 Общий баланс игроков: <b>{stats.get('total_balance', 0.0):,.2f} монет</b>\n"
                f"⏳ В ожидании вывода: <b>{stats.get('pending_withdrawals', 0)}</b>"
            )
        elif stats_type == "commands":
            top_actions = await self.get_action_stats()
            header = "<b>📈 Топ-10 действий пользователей</b>\n\n"
            if not top_actions:
                text = header + "<i>Нет данных о действиях.</i>"
            else:
                actions_list = [f"<code>{action}</code> - {count} раз" for action, count in top_actions]
                text = header + "\n".join(actions_list)
        else:
            # Возвращаем меню статистики, если тип неизвестен
            logger.warning(f"Запрошен неизвестный тип статистики: {stats_type}")
            return "Выберите категорию для просмотра:", get_stats_menu_keyboard()
        
        return text, get_back_to_admin_menu_keyboard()

    # --- Приватные методы сбора данных ---
    async def get_global_stats(self) -> dict:
        """Собирает глобальную статистику по пользователям."""
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

    async def get_game_stats(self) -> Dict[str, Any]:
        """Собирает статистику по игровому модулю."""
        stats_key = self.keys.game_stats()
        game_stats = await self.redis.hgetall(stats_key)
        
        # Суммируем балансы всех игроков
        total_balance = await self.redis.zscore(self.keys.game_leaderboard(), "global_sum") or 0.0
        
        return {
            "active_sessions": int(game_stats.get("active_sessions", 0)),
            "pending_withdrawals": int(game_stats.get("pending_withdrawals", 0)),
            "total_balance": float(total_balance)
        }

    async def get_action_stats(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Получает топ-N самых частых действий пользователей."""
        actions_raw = await self.redis.zrevrange("stats:actions", 0, top_n - 1, withscores=True)
        return [(action, int(score)) for action, score in actions_raw]

    # --- Навигация в админ-панели ---
    async def get_main_menu_content(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает контент для главного меню админ-панели."""
        # Упрощенная проверка роли, т.к. фильтр уже отработал
        user_role = UserRole.SUPER_ADMIN if user_id in self.settings.admin_ids else UserRole.ADMIN
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard
        
    # --- НОВЫЙ МЕТОД: Изменение баланса ---
    async def change_user_game_balance(self, user_id: int, amount: float) -> Optional[float]:
        """
        Атомарно изменяет игровой баланс пользователя и возвращает новый баланс.
        Возвращает None, если профиль пользователя не найден.
        """
        profile_key = self.keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            logger.warning(f"Попытка изменить баланс для несуществующего игрового профиля: user_id={user_id}")
            return None

        # Атомарно увеличиваем баланс и получаем новое значение
        new_balance = await self.redis.hincrbyfloat(profile_key, "balance", amount)
        # Также обновляем значение в таблице лидеров
        await self.redis.zadd(self.keys.game_leaderboard(), {str(user_id): new_balance})
        
        logger.info(f"Администратор изменил баланс user_id={user_id} на {amount}. Новый баланс: {new_balance}")
        return new_balance

    # --- Системные действия ---
    async def clear_asic_cache(self) -> int:
        """Очищает кэш ASIC-майнеров."""
        # Ищем все ключи, связанные с асиками
        cursor = '0'
        deleted_count = 0
        while cursor != 0:
            cursor, keys = await self.redis.scan(cursor, match=f"{self.keys.asic_hash('*')}", count=1000)
            if keys:
                deleted_count += await self.redis.delete(*keys)
        
        # Также удаляем сортированный сет и ключ последнего обновления
        deleted_count += await self.redis.delete(self.keys.asics_sorted_set(), self.keys.asics_last_update())
        
        logger.info(f"ASIC cache cleared. Deleted {deleted_count} keys.")
        return deleted_count