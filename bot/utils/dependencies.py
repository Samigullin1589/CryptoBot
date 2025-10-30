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
from bot.services.quiz_service import QuizService
from bot.services.market_data_service import MarketDataService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.mining_game_service import MiningGameService
from bot.services.verification_service import VerificationService
from bot.services.ai_content_service import AIContentService
from bot.services.mining_service import MiningService
from bot.services.security_service import SecurityService
from bot.services.moderation_service import ModerationService
from bot.services.coin_list_service import CoinListService
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
    admin_service: AdminService
    user_service: UserService
    price_service: PriceService
    asic_service: AsicService
    news_service: NewsService
    quiz_service: QuizService
    market_data_service: MarketDataService
    crypto_center_service: CryptoCenterService
    mining_game_service: MiningGameService
    verification_service: VerificationService
    ai_content_service: AIContentService
    mining_service: MiningService
    security_service: SecurityService
    moderation_service: ModerationService
    coin_list_service: CoinListService


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
    quiz_service: QuizService = Provide[Container.quiz_service],
    market_data_service: MarketDataService = Provide[Container.market_data_service],
    crypto_center_service: CryptoCenterService = Provide[Container.crypto_center_service],
    mining_game_service: MiningGameService = Provide[Container.mining_game_service],
    verification_service: VerificationService = Provide[Container.verification_service],
    ai_content_service: AIContentService = Provide[Container.ai_content_service],
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
    data["deps"] = Deps(
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
    
    # Добавляем отдельные сервисы для обратной совместимости
    data["market_data_service"] = market_data_service
    data["price_service"] = price_service
    data["coin_list_service"] = coin_list_service
    data["user_service"] = user_service
    data["admin_service"] = admin_service
    
    return await handler(event, data)