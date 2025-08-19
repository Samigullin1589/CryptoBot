# bot/services/admin_service.py
# Дата обновления: 19.08.2025
# Версия: 2.0.0
# Описание: Сервис для выполнения административных задач, сбора статистики и управления ботом.

from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.keyboards.admin_keyboards import (get_admin_menu_keyboard,
                                           get_back_to_admin_menu_keyboard,
                                           get_stats_menu_keyboard)
from bot.utils.dependencies import get_bot_instance, get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import UserRole


class AdminService:
    """
    Централизованный сервис для всей административной логики, включая:
    - Сбор и форматирование статистики.
    - Управление пользователями и игровыми данными.
    - Системные действия (очистка кэша).
    - Отправка уведомлений администраторам.
    """

    def __init__(self):
        """
        Инициализирует сервис, получая зависимости из централизованного источника.
        """
        self.redis: Redis = get_redis_client()
        self.bot: Bot = get_bot_instance()
        self.keys = KeyFactory

    async def track_action(self, user_id: int, action_name: str):
        """
        Отслеживает действие пользователя (команду, нажатие кнопки) для сбора статистики.
        """
        try:
            await self.redis.zincrby(self.keys.actions_stats(), 1, action_name)
        except Exception as e:
            logger.error(f"Не удалось отследить действие '{action_name}' для пользователя {user_id}: {e}")

    async def notify_admins(self, message: str, **kwargs):
        """
        Отправляет асинхронное уведомление всем администраторам из конфига.
        """
        logger.info(f"Отправка уведомления администраторам: '{message[:50]}...'")
        for admin_id in settings.ADMIN_IDS:
            with suppress(Exception):  # Игнорируем ошибки, если админ заблокировал бота
                await self.bot.send_message(admin_id, message, **kwargs)

    async def get_stats_page_content(self, stats_type: str) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Возвращает отформатированный текст и клавиатуру для указанного раздела статистики.
        """
        formatters = {
            "general": self._format_general_stats,
            "mining": self._format_game_stats,
            "commands": self._format_action_stats,
        }
        formatter = formatters.get(stats_type)

        if formatter:
            text = await formatter()
            keyboard = get_back_to_admin_menu_keyboard()
        else:
            logger.warning(f"Запрошен неизвестный тип статистики: {stats_type}")
            text = "Выберите категорию для просмотра:"
            keyboard = get_stats_menu_keyboard()
        
        return text, keyboard

    async def _format_general_stats(self) -> str:
        """Форматирует блок с общей статистикой."""
        stats = await self._get_global_stats()
        return (
            "<b>📊 Общая статистика</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['users_total']}</b>\n"
            f"☀️ Активных за день: <b>{stats['users_active_day']}</b>\n"
            f"📅 Активных за неделю: <b>{stats['users_active_week']}</b>"
        )

    async def _format_game_stats(self) -> str:
        """Форматирует блок с игровой статистикой."""
        stats = await self._get_game_stats()
        total_balance_formatted = f"{stats.get('total_balance', 0.0):,.2f}".replace(",", " ")
        return (
            "<b>🎮 Игровая статистика</b>\n\n"
            f"🕹 Активных сессий: <b>{stats.get('active_sessions', 0)}</b>\n"
            f"💰 Общий баланс игроков: <b>{total_balance_formatted} монет</b>\n"
            f"⏳ В ожидании вывода: <b>{stats.get('pending_withdrawals', 0)}</b>"
        )

    async def _format_action_stats(self) -> str:
        """Форматирует блок со статистикой по действиям пользователей."""
        top_actions = await self._get_action_stats()
        header = "<b>📈 Топ-10 действий пользователей</b>\n\n"
        if not top_actions:
            return header + "<i>Нет данных о действиях.</i>"
        
        actions_list = [f"<code>{action}</code> - {count} раз" for action, count in top_actions]
        return header + "\n".join(actions_list)

    async def _get_global_stats(self) -> Dict[str, int]:
        """Собирает из Redis глобальную статистику по пользователям."""
        now = datetime.utcnow()
        day_key = self.keys.daily_active_users(now)
        week_key = self.keys.weekly_active_users(now)

        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.scard(self.keys.all_users_set())
            pipe.scard(day_key)
            pipe.scard(week_key)
            results = await pipe.execute()

        return {
            "users_total": results[0],
            "users_active_day": results[1],
            "users_active_week": results[2],
        }

    async def _get_game_stats(self) -> Dict[str, Any]:
        """Собирает из Redis статистику по игровому модулю."""
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.hgetall(self.keys.game_stats())
            pipe.get(self.keys.game_total_balance())
            results = await pipe.execute()
            
        game_stats_raw = results[0]
        total_balance = float(results[1] or 0.0)

        return {
            "active_sessions": int(game_stats_raw.get("active_sessions", 0)),
            "pending_withdrawals": int(game_stats_raw.get("pending_withdrawals", 0)),
            "total_balance": total_balance,
        }

    async def _get_action_stats(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Получает топ-N самых частых действий пользователей из Redis."""
        actions_raw = await self.redis.zrevrange(
            self.keys.actions_stats(), 0, top_n - 1, withscores=True
        )
        return [(action, int(score)) for action, score in actions_raw]

    async def get_main_menu_content(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает контент для главного меню админ-панели."""
        user_role = UserRole.SUPER_ADMIN if user_id in settings.ADMIN_IDS else UserRole.ADMIN
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard

    async def change_user_game_balance(self, user_id: int, amount: float, admin_id: int) -> Optional[float]:
        """
        Атомарно изменяет игровой баланс пользователя и возвращает новый баланс.
        Также обновляет общий баланс всех игроков.
        """
        profile_key = self.keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            logger.warning(f"Админ {admin_id} пытался изменить баланс для несуществующего профиля: {user_id}")
            return None

        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.hincrbyfloat(profile_key, "balance", amount)
                pipe.zincrby(self.keys.game_leaderboard(), amount, str(user_id))
                pipe.incrbyfloat(self.keys.game_total_balance(), amount)
                results = await pipe.execute()
            
            new_balance = results[0]
            logger.success(
                f"Админ {admin_id} изменил баланс user_id={user_id} на {amount}. "
                f"Новый баланс: {new_balance}"
            )
            return new_balance
        except Exception as e:
            logger.exception(f"Ошибка при изменении баланса для user_id={user_id} админом {admin_id}: {e}")
            return None

    async def clear_asic_cache(self) -> int:
        """
        Полностью очищает кэш ASIC-майнеров, используя сканирование ключей.
        """
        logger.info("Запущена задача очистки кэша ASIC.")
        deleted_count = 0
        async for key in self.redis.scan_iter(match="asic:*"):
            deleted_count += await self.redis.delete(key)
        
        # Дополнительно удаляем служебные ключи
        service_keys = [self.keys.asics_sorted_set(), self.keys.asics_last_update()]
        deleted_count += await self.redis.delete(*service_keys)
        
        logger.success(f"Кэш ASIC очищен. Удалено ключей: {deleted_count}.")
        return deleted_count