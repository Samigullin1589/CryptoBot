# bot/middlewares/dependencies.py
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger

from bot.containers import Container
from bot.utils.dependencies import Deps


class DependenciesMiddleware(BaseMiddleware):
    """
    Middleware для внедрения зависимостей из DI-контейнера в обработчики.
    Все сервисы из контейнера становятся доступны как kwargs в handlers.
    """

    def __init__(self, container: Container):
        super().__init__()
        self.container = container
        logger.info("✅ DependenciesMiddleware initialized")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Внедряем сервисы в data для доступа из handlers.
        """
        try:
            from bot.utils.keys import KeyFactory
            
            # Получаем ресурсы
            settings = self.container.config()
            redis = await self.container.redis_client()
            
            # Получаем сервисы
            try:
                admin_service = self.container.admin_service()
            except Exception as e:
                logger.error(f"Failed to get admin_service: {e}")
                admin_service = None
                
            try:
                user_service = self.container.user_service()
            except Exception as e:
                logger.error(f"Failed to get user_service: {e}")
                user_service = None
                
            try:
                price_service = self.container.price_service()
            except Exception as e:
                logger.error(f"Failed to get price_service: {e}")
                price_service = None
                
            try:
                asic_service = self.container.asic_service()
            except Exception as e:
                logger.error(f"Failed to get asic_service: {e}")
                asic_service = None
                
            try:
                news_service = self.container.news_service()
            except Exception as e:
                logger.error(f"Failed to get news_service: {e}")
                news_service = None
                
            try:
                quiz_service = self.container.quiz_service()
            except Exception as e:
                logger.error(f"Failed to get quiz_service: {e}")
                quiz_service = None
                
            try:
                market_data_service = self.container.market_data_service()
            except Exception as e:
                logger.error(f"Failed to get market_data_service: {e}")
                market_data_service = None
                
            try:
                crypto_center_service = self.container.crypto_center_service()
            except Exception as e:
                logger.error(f"Failed to get crypto_center_service: {e}")
                crypto_center_service = None
                
            try:
                mining_game_service = self.container.mining_game_service()
            except Exception as e:
                logger.error(f"Failed to get mining_game_service: {e}")
                mining_game_service = None
                
            try:
                verification_service = self.container.verification_service()
            except Exception as e:
                logger.error(f"Failed to get verification_service: {e}")
                verification_service = None
                
            try:
                ai_content_service = self.container.ai_content_service()
            except Exception as e:
                logger.error(f"Failed to get ai_content_service: {e}")
                ai_content_service = None
                
            try:
                mining_service = self.container.mining_service()
            except Exception as e:
                logger.error(f"Failed to get mining_service: {e}")
                mining_service = None
                
            try:
                security_service = self.container.security_service()
            except Exception as e:
                logger.error(f"Failed to get security_service: {e}")
                security_service = None
                
            try:
                moderation_service = self.container.moderation_service()
            except Exception as e:
                logger.error(f"Failed to get moderation_service: {e}")
                moderation_service = None
                
            try:
                coin_list_service = self.container.coin_list_service()
            except Exception as e:
                logger.error(f"Failed to get coin_list_service: {e}")
                coin_list_service = None
            
            # Создаем объект Deps со всеми зависимостями
            deps = Deps(
                settings=settings,
                redis=redis,
                keys=KeyFactory,
                admin_service=admin_service,
                user_service=user_service,
                price_service=price_service,
                asic_service=asic_service,
                news_service=news_service,
                quiz_service=quiz_service,
                market_data_service=market_data_service,
                crypto_center_service=crypto_center_service,
                mining_game_service=mining_game_service,
                verification_service=verification_service,
                ai_content_service=ai_content_service,
                mining_service=mining_service,
                security_service=security_service,
                moderation_service=moderation_service,
                coin_list_service=coin_list_service,
            )
            
            # Добавляем deps в data
            data["deps"] = deps
            
            # Добавляем отдельные сервисы для обратной совместимости
            data["container"] = self.container
            data["market_data_service"] = market_data_service
            data["price_service"] = price_service
            data["coin_list_service"] = coin_list_service
            data["user_service"] = user_service
            data["admin_service"] = admin_service
            data["settings"] = settings
            data["redis"] = redis
            
        except Exception as e:
            logger.error(f"Critical error in DependenciesMiddleware: {e}", exc_info=True)
            # Устанавливаем пустой deps чтобы хэндлер не упал
            data["deps"] = None
        
        return await handler(event, data)