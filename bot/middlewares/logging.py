"""
Middleware для логирования всех обновлений и ошибок.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, TelegramObject
import logging

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования входящих обновлений."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события с логированием.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Событие Telegram
            data: Данные контекста
            
        Returns:
            Результат обработки
        """
        # Логируем входящее обновление
        if isinstance(event, Update):
            update_info = self._get_update_info(event)
            logger.info(f"📨 Received update: {update_info}")
        
        try:
            # Вызываем следующий обработчик
            result = await handler(event, data)
            return result
            
        except Exception as e:
            logger.error(
                f"❌ Error processing update: {e}",
                exc_info=True,
                extra={"update": event.model_dump() if hasattr(event, "model_dump") else str(event)}
            )
            raise
    
    @staticmethod
    def _get_update_info(update: Update) -> str:
        """
        Извлечение информации об обновлении для логирования.
        
        Args:
            update: Обновление Telegram
            
        Returns:
            Строка с информацией об обновлении
        """
        if update.message:
            user = update.message.from_user
            text = update.message.text or "[media]"
            return f"Message from @{user.username} ({user.id}): {text}"
        elif update.callback_query:
            user = update.callback_query.from_user
            data = update.callback_query.data
            return f"Callback from @{user.username} ({user.id}): {data}"
        elif update.inline_query:
            user = update.inline_query.from_user
            query = update.inline_query.query
            return f"Inline query from @{user.username} ({user.id}): {query}"
        else:
            return f"Update type: {update.event_type}"