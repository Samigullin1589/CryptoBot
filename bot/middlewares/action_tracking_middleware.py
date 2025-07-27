# ===============================================================
# Файл: bot/middlewares/action_tracking_middleware.py (НОВЫЙ ФАЙЛ)
# Описание: Middleware для интеллектуального отслеживания действий
# пользователя (команд и нажатий на кнопки). Заменяет старый
# StatsMiddleware.
# ===============================================================
import logging
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery

from bot.services.admin_service import AdminService

logger = logging.getLogger(__name__)

class ActionTrackingMiddleware(BaseMiddleware):
    """
    Middleware для сбора статистики использования команд и кнопок.
    
    Ключевые особенности:
    - Интеллектуальный парсинг: Корректно распознает действия из
      текстовых команд и структурированных callback-данных.
    - Делегирование: Вся логика записи статистики инкапсулирована
      в AdminService.
    """
    def __init__(self, admin_service: AdminService):
        self.admin_service = admin_service

    def _parse_action_name(self, event: Update) -> Optional[str]:
        """
        Извлекает стандартизированное имя действия из события.
        
        :param event: Входящее событие Update.
        :return: Имя действия или None, если действие не удалось определить.
        """
        if event.message and event.message.text:
            text = event.message.text
            if text.startswith('/'):
                return text.split()[0] # e.g., "/start"
            # Можно добавить маппинг текста кнопок к действиям, если нужно
            # '💹 Курс' -> 'nav:price'
            
        if event.callback_query and event.callback_query.data:
            data = event.callback_query.data
            # Преобразуем 'domain:action:value' в 'domain:action' для агрегации
            # Например, 'game_nav:shop:1' и 'game_nav:shop:2' будут считаться как 'game_nav:shop'
            parts = data.split(':')
            if len(parts) > 1:
                return f"{parts[0]}:{parts[1]}" # e.g., "nav:price", "game_action:start"
            return data # Для простых колбэков вроде "back_to_main_menu"
            
        return None

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Вызывается для каждого входящего события.
        """
        user = data.get('event_from_user')
        
        # Если есть пользователь, пытаемся отследить его действие
        if user:
            action_name = self._parse_action_name(event)
            if action_name:
                try:
                    # Делегируем запись статистики сервису
                    await self.admin_service.track_action(user.id, action_name)
                    logger.debug(f"Tracked action '{action_name}' for user {user.id}")
                except Exception as e:
                    logger.error(f"Failed to track action '{action_name}' for user {user.id}: {e}")

        # Передаем управление дальше, независимо от результата отслеживания
        return await handler(event, data)
