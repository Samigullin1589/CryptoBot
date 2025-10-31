# bot/utils/dependencies.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram.types import TelegramObject
from dependency_injector.wiring import Provide, inject
from redis.asyncio import Redis

from bot.containers import Container
from bot.services.admin_service import AdminService
from bot.services.user_service import UserService
from bot.services.price_service import PriceService
from bot.services.asic_service import AsicService
from bot.services.news_service import NewsService
from bot.services.market_data_service import MarketDataService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.mining_game_service import MiningGameService
from bot.services.verification_service import VerificationService
from bot.services.mining_service import MiningService
from bot.services.security_service import SecurityService
from bot.services.moderation_service import ModerationService
from bot.services.coin_list_service import CoinListService
from bot.services.achievement_service import AchievementService
from bot.config.settings import Settings
from bot.utils.keys import KeyFactory


@dataclass
class Deps:
    """
    Контейнер для зависимостей, передаваемый в хэндлеры.
    Все сервисы и ресурсы доступны через этот dataclass.
    """
    settings: Settings
    redis: Redis
    keys: type[KeyFactory]
    admin_service: Optional[AdminService] = None
    user_service: Optional[UserService] = None
    price_service: Optional[PriceService] = None
    asic_service: Optional[AsicService] = None
    news_service: Optional[NewsService] = None
    market_data_service: Optional[MarketDataService] = None
    crypto_center_service: Optional[CryptoCenterService] = None
    mining_game_service: Optional[MiningGameService] = None
    verification_service: Optional[VerificationService] = None
    mining_service: Optional[MiningService] = None
    security_service: Optional[SecurityService] = None
    moderation_service: Optional[ModerationService] = None
    coin_list_service: Optional[CoinListService] = None
    achievement_service: Optional[AchievementService] = None
    quiz_service: Optional[Any] = None
    ai_content_service: Optional[Any] = None


@inject
async def dependencies_middleware(
    handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: Dict[str, Any],
    settings: Settings = Provide[Container.config],
    redis: Redis = Provide[Container.redis_client],
    admin_service: AdminService = Provide[Container.admin_service],
    user_service: UserService = Provide[Container.user_service],
    price_service: PriceService = Provide[Container.price_service],
    asic_service: AsicService = Provide[Container.asic_service],
    news_service: NewsService = Provide[Container.news_service],
    market_data_service: MarketDataService = Provide[Container.market_data_service],
    crypto_center_service: CryptoCenterService = Provide[Container.crypto_center_service],
    mining_game_service: MiningGameService = Provide[Container.mining_game_service],
    verification_service: VerificationService = Provide[Container.verification_service],
    mining_service: MiningService = Provide[Container.mining_service],
    security_service: SecurityService = Provide[Container.security_service],
    moderation_service: ModerationService = Provide[Container.moderation_service],
    coin_list_service: CoinListService = Provide[Container.coin_list_service],
) -> Any:
    """
    Middleware для внедрения всех зависимостей в data.
    
    Args:
        handler: Следующий обработчик в цепочке
        event: Telegram событие
        data: Данные для передачи в обработчик
        
    Returns:
        Результат обработчика
    """
    quiz_service = None
    ai_content_service = None
    achievement_service = None
    
    try:
        from bot.services.quiz_service import QuizService
        if hasattr(Container, 'quiz_service'):
            quiz_service = await Container.quiz_service()
    except (ImportError, AttributeError):
        pass
    
    try:
        from bot.services.ai_content_service import AIContentService
        if hasattr(Container, 'ai_content_service'):
            ai_content_service = await Container.ai_content_service()
    except (ImportError, AttributeError):
        pass
    
    try:
        from bot.services.achievement_service import AchievementService
        if hasattr(Container, 'achievement_service'):
            achievement_service = await Container.achievement_service()
    except (ImportError, AttributeError):
        pass
    
    data["deps"] = Deps(
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
        quiz_service=quiz_service,
        ai_content_service=ai_content_service,
    )
    
    data["market_data_service"] = market_data_service
    data["price_service"] = price_service
    data["coin_list_service"] = coin_list_service
    data["user_service"] = user_service
    data["admin_service"] = admin_service
    
    return await handler(event, data)