# bot/middlewares/dependencies.py
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger

from bot.containers import Container
from bot.utils.dependencies import Deps


class DependenciesMiddleware(BaseMiddleware):
    """Middleware для внедрения зависимостей из DI-контейнера в обработчики"""

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
        try:
            from bot.utils.keys import KeyFactory
            
            settings = self.container.config()
            redis = await self.container.redis_client()
            
            admin_service = None
            user_service = None
            price_service = None
            asic_service = None
            news_service = None
            market_data_service = None
            crypto_center_service = None
            mining_game_service = None
            verification_service = None
            mining_service = None
            security_service = None
            moderation_service = None
            coin_list_service = None
            achievement_service = None
            ai_content_service = None
            quiz_service = None
            
            try:
                admin_service = self.container.admin_service()
            except Exception as e:
                logger.error(f"Failed to get admin_service: {e}")
                
            try:
                user_service = self.container.user_service()
            except Exception as e:
                logger.error(f"Failed to get user_service: {e}")
                
            try:
                price_service = self.container.price_service()
            except Exception as e:
                logger.error(f"Failed to get price_service: {e}")
                
            try:
                asic_service = self.container.asic_service()
            except Exception as e:
                logger.error(f"Failed to get asic_service: {e}")
                
            try:
                news_service = self.container.news_service()
            except Exception as e:
                logger.error(f"Failed to get news_service: {e}")
                
            try:
                market_data_service = self.container.market_data_service()
            except Exception as e:
                logger.error(f"Failed to get market_data_service: {e}")
                
            try:
                crypto_center_service = self.container.crypto_center_service()
            except Exception as e:
                logger.error(f"Failed to get crypto_center_service: {e}")
                
            try:
                mining_game_service = self.container.mining_game_service()
            except Exception as e:
                logger.error(f"Failed to get mining_game_service: {e}")
                
            try:
                verification_service = self.container.verification_service()
            except Exception as e:
                logger.error(f"Failed to get verification_service: {e}")
                
            try:
                mining_service = self.container.mining_service()
            except Exception as e:
                logger.error(f"Failed to get mining_service: {e}")
                
            try:
                security_service = self.container.security_service()
            except Exception as e:
                logger.error(f"Failed to get security_service: {e}")
                
            try:
                moderation_service = self.container.moderation_service()
            except Exception as e:
                logger.error(f"Failed to get moderation_service: {e}")
                
            try:
                coin_list_service = self.container.coin_list_service()
            except Exception as e:
                logger.error(f"Failed to get coin_list_service: {e}")
                
            try:
                achievement_service = self.container.achievement_service()
            except Exception as e:
                logger.error(f"Failed to get achievement_service: {e}")
            
            try:
                ai_content_service = self.container.ai_content_service()
            except Exception as e:
                logger.error(f"Failed to get ai_content_service: {e}")
            
            try:
                quiz_service = self.container.quiz_service()
            except Exception as e:
                logger.error(f"Failed to get quiz_service: {e}")
            
            deps = Deps(
                settings=settings,
                redis=redis,
                keys=KeyFactory,
                admin_service=admin_service,
                user_service=user_service,
                price_service=price_service,
                asic_service=asic_service,
                news_service=news_service,
                market_data_service=market_data_service,
                crypto_center_service=crypto_center_service,
                mining_game_service=mining_game_service,
                verification_service=verification_service,
                mining_service=mining_service,
                security_service=security_service,
                moderation_service=moderation_service,
                coin_list_service=coin_list_service,
                achievement_service=achievement_service,
                ai_content_service=ai_content_service,
                quiz_service=quiz_service,
            )
            
            data["deps"] = deps
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
            data["deps"] = None
        
        return await handler(event, data)