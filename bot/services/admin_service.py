# ===============================================================
# Файл: bot/services/admin_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Единый сервис для всей логики администрирования.
# Заменяет AdminStatsService, устраняет опасные команды KEYS
# и внедряет систему атомарных счетчиков для безопасного и
# мгновенного сбора статистики.
# ===============================================================
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List

import redis.asyncio as redis
from aiogram.types import InlineKeyboardMarkup

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
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    # --- Методы для отслеживания статистики (вызываются извне) ---

    async def track_action(self, user_id: int, action_name: str):
        """Отслеживает использование команды или нажатие на кнопку."""
        # Используем ZINCRBY для инкремента счетчика в отсортированном сете
        await self.redis.zincrby("stats:actions", 1, action_name)

    async def track_new_user(self, user_id: int):
        """Отмечает появление нового пользователя."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        # Используем SADD для добавления в множество всех пользователей
        if await self.redis.sadd("users:known", user_id):
            # Если пользователь действительно новый, добавляем в ZSET для статистики по дате
            await self.redis.zadd("stats:user_first_seen", {str(user_id): timestamp})

    # --- Методы для получения и форматирования страниц статистики ---

    async def get_stats_page_content(self, stats_type: str) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Возвращает отформатированный текст и клавиатуру для указанной страницы статистики.
        """
        if stats_type == "general":
            stats = await self._get_general_stats()
            text = (
                "<b>📊 Общая статистика</b>\n\n"
                f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
                f"🚀 Новых за 24 часа: <b>{stats['new_24h']}</b>\n"
                f"🏃‍♂️ Активных за 24 часа: <b>{stats['active_24h']}</b>"
            )
        elif stats_type == "mining":
            stats = await self._get_mining_stats()
            text = (
                "<b>💎 Статистика 'Виртуального Майнинга'</b>\n\n"
                f"⚡️ Активных сессий сейчас: <b>{stats['active_sessions']}</b>\n"
                f"💰 Всего монет на балансах: <b>{stats['total_balance']:.2f}</b>\n"
                f"📤 Всего выведено средств: <b>{stats['total_withdrawn']:.2f}</b>\n"
                f"🤝 Всего успешных рефералов: <b>{stats['total_referrals']}</b>"
            )
        elif stats_type == "commands":
            top_commands = await self._get_command_stats()
            if not top_commands:
                stats_text = "Еще нет данных."
            else:
                stats_text = "\n".join([f"🔹 <code>{cmd}</code> - {score} раз" for cmd, score in top_commands])
            text = f"<b>📈 Топ-10 действий</b>\n\n{stats_text}"
        else:
            raise KeyError(f"Unknown stats type: {stats_type}")
            
        return text, get_back_to_admin_menu_keyboard()

    # --- Приватные методы для сбора данных (безопасные) ---

    async def _get_general_stats(self) -> Dict[str, Any]:
        """Собирает общую статистику, используя безопасные команды."""
        one_day_ago = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
        
        async with self.redis.pipeline() as pipe:
            pipe.scard("users:known")
            pipe.zcount("stats:user_activity", min=one_day_ago, max=-1)
            pipe.zcount("stats:user_first_seen", min=one_day_ago, max=-1)
            results = await pipe.execute()
            
        return {
            "total_users": results[0],
            "active_24h": results[1],
            "new_24h": results[2],
        }

    async def _get_mining_stats(self) -> Dict[str, Any]:
        """Собирает статистику по игре, используя атомарные счетчики."""
        keys = [
            "stats:mining:active_sessions",
            "stats:mining:total_balance",
            "stats:mining:total_withdrawn",
            "stats:mining:total_referrals"
        ]
        # MGET - эффективный способ получить значения нескольких ключей
        values = await self.redis.mget(keys)
        
        return {
            "active_sessions": int(values[0] or 0),
            "total_balance": float(values[1] or 0.0),
            "total_withdrawn": float(values[2] or 0.0),
            "total_referrals": int(values[3] or 0),
        }

    async def _get_command_stats(self) -> List[Tuple[str, int]]:
        """Получает топ-10 самых используемых действий."""
        # ZREVRANGE - эффективная команда для получения топа из отсортированного сета
        top_actions = await self.redis.zrevrange("stats:actions", 0, 9, withscores=True)
        # Корректно декодируем байты в строки для отображения
        return [(cmd.decode('utf-8'), int(score)) for cmd, score in top_actions]

    # --- Системные действия ---

    async def clear_asic_cache(self) -> int:
        """
        Безопасно очищает кэш ASIC, используя SCAN вместо KEYS.
        Возвращает количество удаленных ключей.
        """
        keys_to_delete = []
        # Безопасно итерируемся по ключам, не блокируя Redis
        async for key in self.redis.scan_iter("asic_passport:*"):
            keys_to_delete.append(key)
        
        last_update_key = "asics_last_update_utc"
        if await self.redis.exists(last_update_key):
            keys_to_delete.append(last_update_key)
            
        if not keys_to_delete:
            return 0
            
        return await self.redis.delete(*keys_to_delete)

    # --- Методы для навигации в админ-панели (вызываются из хэндлеров) ---
    
    async def get_main_menu_content(self, user_id: int, user_role: UserRole) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает контент для главного меню админки."""
        # TODO: Добавить логику для получения роли пользователя, если она не передана
        text = "<b>Панель администратора</b>\n\nВыберите раздел:"
        keyboard = get_admin_menu_keyboard(user_role)
        return text, keyboard

    async def get_stats_menu_content(self) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает контент для меню статистики."""
        text = "<b>📊 Статистика</b>\n\nВыберите интересующий вас отчет:"
        keyboard = get_stats_menu_keyboard()
        return text, keyboard

    async def get_system_menu_content(self) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает контент для меню системных действий."""
        text = "<b>⚙️ Системные действия</b>\n\n<b>Внимание:</b> эти действия могут повлиять на работу бота."
        keyboard = get_system_actions_keyboard()
        return text, keyboard
