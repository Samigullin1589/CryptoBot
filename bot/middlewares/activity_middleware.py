# ===============================================================
# Файл: bot/middlewares/activity_middleware.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Middleware для эффективного отслеживания активности
# пользователей. Внедрен механизм троттлинга для снижения
# нагрузки на базу данных.
# ===============================================================
import time
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot.services.user_service import UserService

logger = logging.getLogger(__name__)

# ПРИМЕЧАНИЕ: Этот класс настроек должен быть частью вашего
# основного файла settings.py для централизованного управления.
class ActivitySettings:
    """Настройки для middleware активности."""
    # Обновлять активность пользователя не чаще, чем раз в N секунд
    THROTTLE_SECONDS: int = 60

class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания и поощрения активности пользователей.
    
    Ключевые особенности:
    - Троттлинг: Обновляет "last_seen" не чаще раза в минуту, чтобы
      избежать лишних записей в БД при быстрой отправке сообщений.
    - Делегирование: Вся бизнес-логика находится в UserService.
    """
    def __init__(self, user_service: UserService):
        """
        Инициализирует middleware с сервисом пользователей и кешем для троттлинга.
        """
        self.user_service = user_service
        self.settings = ActivitySettings()
        # Простой кеш для отслеживания времени последнего обновления {user_id: timestamp}
        self.last_update_times: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Вызывается для каждого входящего события.
        """
        # Мы отслеживаем только реальные действия пользователя: сообщения и нажатия на кнопки
        if not (event.message or event.callback_query):
            return await handler(event, data)

        user = data.get('event_from_user')
        chat = data.get('event_chat')

        if not user or not chat:
            return await handler(event, data)

        user_id = user.id
        current_time = time.time()

        # --- Логика троттлинга ---
        # Проверяем, прошло ли достаточно времени с последнего обновления
        last_update = self.last_update_times.get(user_id, 0)
        if current_time - last_update < self.settings.THROTTLE_SECONDS:
            # Если времени прошло недостаточно, просто пропускаем обновление
            return await handler(event, data)

        # --- Обновление активности ---
        try:
            # Делегируем всю логику обновления UserService.
            await self.user_service.update_user_activity(user_id, chat.id)
            
            # Если обновление прошло успешно, записываем новое время в наш кеш
            self.last_update_times[user_id] = current_time
            
            logger.debug(f"Updated activity for user {user_id} in chat {chat.id}")

        except Exception as e:
            # Логируем ошибку, но не останавливаем обработку события
            logger.error(f"Failed to update activity for user {user_id} in chat {chat.id}: {e}")

        # Передаем управление дальше по цепочке обработчиков
        return await handler(event, data)
