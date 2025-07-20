import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update

# Импортируем наш основной сервис для работы с пользователями
from bot.services.user_service import UserService

logger = logging.getLogger(__name__)

class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания и поощрения активности пользователей.
    Интегрирован с UserService для обновления профиля пользователя и его рейтинга доверия.
    """
    def __init__(self, user_service: UserService):
        """
        Инициализирует middleware с сервисом пользователей.
        Больше не зависит от прямого доступа к Redis.
        """
        self.user_service = user_service

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Этот метод вызывается для каждого входящего события (update).
        """
        # Пытаемся получить пользователя и чат из данных, которые предоставляет aiogram
        user = data.get('event_from_user')
        chat = data.get('event_chat')

        # Мы отслеживаем активность только от реальных пользователей и только в чатах (не в личке с ботом)
        if not user or not chat or chat.type == 'private':
            return await handler(event, data)

        try:
            # Делегируем всю логику обновления активности нашему UserService.
            # Это позволяет сохранять middleware "чистым", а всю бизнес-логику держать в сервисе.
            await self.user_service.update_user_activity(user.id, chat.id)
        except Exception as e:
            # Логируем ошибку, но не останавливаем обработку события
            logger.error(f"Не удалось обновить активность пользователя {user.id} в чате {chat.id}: {e}")

        # Передаем управление дальше по цепочке обработчиков
        return await handler(event, data)
