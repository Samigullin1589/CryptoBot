# =================================================================================
# Файл: bot/middlewares/activity_middleware.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Middleware для эффективного отслеживания активности
# пользователей.
# =================================================================================
import time
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot.services.user_service import UserService
# ИЗМЕНЕНО: Импортируем экземпляр настроек из нового файла
from bot.config.config import settings

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
        chat = data.get('event_chat')

        if not user or not chat:
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
            await self.user_service.update_user_activity(user_id, chat.id)
            self.last_update_times[user_id] = current_time
            logger.debug(f"Updated activity for user {user_id} in chat {chat.id}")
        except Exception as e:
            logger.error(f"Failed to update activity for user {user_id} in chat {chat.id}: {e}")

        return await handler(event, data)