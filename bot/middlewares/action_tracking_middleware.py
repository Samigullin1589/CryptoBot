# ===============================================================
# Файл: bot/middlewares/action_tracking_middleware.py
# Версия: ИСПРАВЛЕННАЯ (19.10.2025)
# ===============================================================

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject  # ✅ ИСПРАВЛЕНИЕ 1: добавлен TelegramObject

from bot.services.admin_service import AdminService

logger = logging.getLogger(__name__)

class ActionTrackingMiddleware(BaseMiddleware):
    """
    Middleware для логирования действий пользователя (команды, колбэки).
    """
    def __init__(self, admin_service: AdminService):
        self.admin_service = admin_service

    # ✅ ИСПРАВЛЕНИЕ 2: Message -> TelegramObject в типе handler
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        # Проверяем, что есть пользователь, чьи действия можно отследить
        user = data.get('event_from_user')
        if not user:
            return await handler(event, data)

        action_description = None
        if isinstance(event, Message) and event.text:
            if event.text.startswith('/'):
                action_description = f" вызвал команду: {event.text}"
        elif isinstance(event, CallbackQuery) and event.data:
            action_description = f" нажал кнопку: {event.data}"

        if action_description:
            try:
                # Предполагаем, что у AdminService есть метод для логирования действий
                await self.admin_service.log_user_action(user.id, user.full_name, action_description)
            except Exception as e:
                logger.error(f"Не удалось залогировать действие для user_id={user.id}: {e}")

        return await handler(event, data)