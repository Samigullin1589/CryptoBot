# ===============================================================
# Файл: bot/services/admin_service.py (ИСПРАВЛЕННЫЙ)
# Описание: Исправлена синтаксическая ошибка.
# ===============================================================

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
from bot.utils.keys import KeyFactory
from bot.utils.models import UserRole


class AdminService:
    """
    Централизованный сервис для всей административной логики.
    """

    def __init__(self, redis_client: Redis, bot: Bot):
        """
        Инициализирует сервис с зависимостями.
        """
        self.redis = redis_client
        self.bot = bot
        self.keys = KeyFactory
        logger.info("Сервис AdminService инициализирован.")

    async def track_action(self, user_id: int, action_name: str):
        """
        Отслеживает действие пользователя для сбора статистики.
        """
        try:
            await self.redis.zincrby(self.keys.actions_stats(), 1, action_name)
        except Exception as e:
            logger.error(f"Не удалось отследить действие '{action_name}' для пользователя {user_id}: {e}")

    async def notify_admins(self, message: str, **kwargs):
        """
        Отправляет уведомление всем администраторам.
        """
        logger.info(f"Отправка уведомления администраторам: '{message[:50]}...'")
        for admin_id in settings.admin_ids:
            with suppress(Exception):
                await self.bot.send_message(admin_id, message, **kwargs)

    async def get_stats_page_content(self, stats_type: str) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Возвращает контент для страницы статистики.
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
            text = "Выберите категорию для просмотра:"
            keyboard = get_stats_menu_keyboard()
        
        return text, keyboard

    async def _format_general_stats(self) -> str:
        stats = await self._get_global_stats()
        return (
            "<b>📊 Общая статистика</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['users_total']}</b>\n"
            f"☀️ Активных за день: <b>{stats['users_active_day']}</b>\n"
            f"📅 Активных за неделю: <b>{stats['users_active_week']}</b>"
        )

    async def _format_game_stats(self) -> str:
        stats = await self._get_game_stats()
        total_balance_formatted = f"{stats.get('total_balance', 0.0):,.2f}".replace(",", " ")
        return (
            "<b>🎮 Игровая статистика</b>\n\n"
            f"🕹 Активных сессий: <b>{stats.get('active_sessions', 0)}</b>\n"
            f"💰 Общий баланс игроков: <b>{total_balance_formatted} монет</b>\n"
            f"⏳ В ожидании вывода: <b>{stats.get('pending_withdrawals', 0)}</b>"
        )

    async def _format_action_stats(self) -> str:
        top_actions = await self._get_action_stats()
        header = "<b>📈 Топ-10 действий пользователей</b>\n\n"
        if not top_actions:
            return header + "<i>Нет данных о действиях.</i>"
        
        actions_list = [f"<code>{action}</code> - {count} раз" for action, count in top_actions]
        return header + "\n".join(actions_list)

    async def _get_global_stats(self) -> Dict[str, int]:
        now = datetime.utcnow()
        day_key = f"stats:active_users:day:{now.strftime('%Y-%m-%d')}"
        week_key = f"stats:active_users:week:{now.strftime('%Y-%U')}"

        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.scard(self.keys.all_users_set())
            pipe.scard(day_key)
            pipe.scard(week_key)
            results = await pipe.execute()

        return {
            "users_total": results[0], "users_active_day": results[1], "users_active_week": results[2],
        }

    async def _get_game_stats(self) -> Dict[str, Any]:
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.hgetall(self.keys.game_stats())
            pipe.get(self.keys.game_total_balance())
            results = await pipe.execute()
            
        game_stats_raw = results[0] or {}
        total_balance = float(results[1] or 0.0)

        return {
            "active_sessions": int(game_stats_raw.get("active_sessions", 0)),
            "pending_withdrawals": int(game_stats_raw.get("pending_withdrawals", 0)),
            "total_balance": total_balance,
        }

    async def _get_action_stats(self, top_n: int = 10) -> List[Tuple[str, int]]:
        actions_raw = await self.redis.zrevrange(self.keys.actions_stats(), 0, top_n - 1, withscores=True)
        return [(action, int(score)) for action, score in actions_raw]

    async def get_main_menu_content(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        user_role = UserRole.SUPER_ADMIN if user_id in settings.admin_ids else UserRole.ADMIN
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard

    async def change_user_game_balance(self, user_id: int, amount: float, admin_id: int) -> Optional[float]:
        profile_key = self.keys.user_game_profile(user_id)
        if not await self.redis.exists(profile_key):
            return None

        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.hincrbyfloat(profile_key, "balance", amount)
                pipe.zincrby(self.keys.game_leaderboard(), amount, str(user_id))
                pipe.incrbyfloat(self.keys.game_total_balance(), amount)
                results = await pipe.execute()
            
            new_balance = results[0]
            logger.success(f"Админ {admin_id} изменил баланс user_id={user_id} на {amount}. Новый баланс: {new_balance}")
            return new_balance
        except Exception as e:
            # ===============================================================
            # ИСПРАВЛЕНИЕ ЗДЕСЬ: Добавлена закрывающая кавычка и скобка
            # ===============================================================
            logger.exception(f"Ошибка при изменении баланса для user_id={user_id} админом {admin_id}: {e}")
            return None

    async def clear_asic_cache(self) -> int:
        logger.info("Запущена задача очистки кэша ASIC.")
        deleted_count = 0
        async for key in self.redis.scan_iter(match="asic:*"):
            deleted_count += await self.redis.delete(key)
        
        service_keys = [self.keys.asics_sorted_set(), self.keys.asics_last_update()]
        deleted_count += await self.redis.delete(*service_keys)
        
        logger.success(f"Кэш ASIC очищен. Удалено ключей: {deleted_count}.")
        return deleted_count