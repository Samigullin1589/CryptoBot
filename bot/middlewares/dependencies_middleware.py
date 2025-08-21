# src/bot/middlewares/dependencies_middleware.py
"""
Middleware для внедрения зависимостей из контейнера в обработчики.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from dependency_injector.wiring import Provide, inject

from bot.containers import Container
from bot.services.user_service import UserService


class DependenciesMiddleware(BaseMiddleware):
    """
    Промежуточный слой, который извлекает сервисы из контейнера
    и передает их в хендлеры через kwargs.
    """
    # Мы не будем внедрять зависимости в сам middleware,
    # а будем передавать их в конструкторе.
    # Это более явный и контролируемый подход.
    def __init__(self, user_service: UserService):
        super().__init__()
        self.user_service = user_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Выполняет middleware.

        Добавляет в `data` экземпляры сервисов, чтобы они были доступны
        в последующих middleware и хендлерах.
        """
        # Добавляем сервисы в `data`. Теперь в хендлерах можно будет
        # получить их через аргументы функции.
        data["user_service"] = self.user_service
        # ... можно добавить и другие часто используемые сервисы,
        # но лучше полагаться на @inject для чистоты.

        # Также можно выполнить какие-то действия с пользователем,
        # например, зарегистрировать его при первом обращении.
        user = data.get("event_from_user")
        if user:
            await self.user_service.get_or_create_user(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name,
            )

        return await handler(event, data)