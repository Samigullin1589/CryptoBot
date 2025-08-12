# =================================================================================
# Файл: bot/middlewares/activity_middleware.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Middleware для эффективного отслеживания активности
# пользователей.
# ИСПРАВЛЕНИЕ: Изменен путь импорта 'settings' для соответствия новой архитектуре.
# =================================================================================
import time
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot.services.user_service import UserService
# ИСПРАВЛЕНО: Импортируем 'settings' из нового единого источника
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания и поощрения активности пользователей.
    """
    def __init__(self, user_service: UserService):
        self.user_service = user_service
        # Простой кеш для отслеживания времени последнего обновления {user_id: timestamp}
        self.last_update_times: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Отслеживаем только реальные действия пользователя
        if not (event.message or event.callback_query):
            return await handler(event, data)

        user = data.get('event_from_user')
        if not user:
            return await handler(event, data)

        user_id = user.id
        current_time = time.time()

        # --- Логика троттлинга ---
        # Обновлять активность не чаще раза в 60 секунд
        throttle_seconds = 60 
        last_update = self.last_update_times.get(user_id, 0)
        if current_time - last_update < throttle_seconds:
            return await handler(event, data)

        # --- Обновление активности ---
        try:
            await self.user_service.update_user_activity(user_id)
            self.last_update_times[user_id] = current_time
            logger.debug(f"Updated activity for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to update activity for user {user_id}: {e}")

        return await handler(event, data)