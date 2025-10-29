# =================================================================================
# bot/containers.py
# Версия: PRODUCTION v3.0.0 (29.10.2025) - Distinguished Engineer
# ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная работа с providers.Resource
# ✅ ДОБАВЛЕНО: Методы init_resources() и shutdown_resources()
# ✅ ИСПРАВЛЕНО: Правильная передача BOT_TOKEN
# =================================================================================

import logging
from typing import AsyncIterator

from dependency_injector import containers, providers
from redis.asyncio import Redis
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config.settings import Settings
from bot.services.achievement_service import AchievementService
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.coin_alias_service import CoinAliasService
from bot.services.coin_list_service import CoinListService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.market_data_service import MarketDataService
from bot.services.mining_game_service import MiningGameService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.user_service import UserService
from bot.services.verification_service import VerificationService
from bot.services.ai_content_service import AIContentService
from bot.utils.http_client import HttpClient
from bot.services.parser_service import ParserService
from bot.services.mining_service import MiningService
from bot.services.moderation_service import ModerationService
from bot.services.security_service import SecurityService
from bot.services.image_vision_service import ImageVisionService

logger = logging.getLogger(__name__)


# =================================================================================
# RESOURCE FACTORIES
# =================================================================================

async def init_redis_client(url: str) -> AsyncIterator[Redis]:
    """
    Фабрика для создания Redis клиента.
    
    Args:
        url: Redis URL
        
    Yields:
        Redis клиент
    """
    client = await Redis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    
    try:
        await client.ping()
        logger.info("✅ Redis client initialized")
        yield client
    finally:
        await client.close()
        logger.info("✅ Redis client closed")


async def init_http_client(config: dict) -> AsyncIterator[HttpClient]:
    """
    Фабрика для создания HTTP клиента.
    
    Args:
        config: Конфигурация endpoints
        
    Yields:
        HTTP клиент
    """
    client = HttpClient(config=config)
    
    try:
        logger.info("✅ HTTP client initialized")
        yield client
    finally:
        await client.close()
        logger.info("✅ HTTP client closed")


async def init_bot(token: str) -> AsyncIterator[Bot]:
    """
    Фабрика для создания Bot.
    
    Args:
        token: Telegram Bot Token
        
    Yields:
        Bot instance
    """
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    try:
        me = await bot.get_me()
        logger.info(f"✅ Bot initialized: @{me.username} (ID: {me.id})")
        yield bot
    finally:
        if bot.session:
            await bot.session.close()
        logger.info("✅ Bot session closed")


# =================================================================================
# MAIN CONTAINER
# =================================================================================

class Container(containers.DeclarativeContainer):
    """
    Основной контейнер приложения для внедрения зависимостей.
    
    ✅ ИСПРАВЛЕНО: Использование правильных фабрик для ресурсов
    """
    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot.main", 
            "bot.utils.dependencies", 
            "bot.jobs.scheduled_tasks",
        ],
        packages=[
            "bot.handlers", 
            "bot.middlewares",
        ],
    )

    # ==================== КОНФИГУРАЦИЯ ====================
    config = providers.Singleton(Settings)

    # ==================== BOT TOKEN ====================
    bot_token = providers.Callable(
        lambda cfg: cfg.BOT_TOKEN.get_secret_value() if cfg.BOT_TOKEN else "",
        config
    )

    # ==================== РЕСУРСЫ (КРИТИЧНО!) ====================
    
    # Redis Client с правильной фабрикой
    redis_client = providers.Resource(
        init_redis_client,
        url=config.provided.REDIS_URL
    )

    # HTTP Client с правильной фабрикой
    http_client = providers.Resource(
        init_http_client,
        config=config.provided.endpoints
    )

    # Bot с правильной фабрикой
    bot = providers.Resource(
        init_bot,
        token=bot_token
    )

    # ==================== СЕРВИСЫ ====================
    
    ai_content_service = providers.Singleton(
        AIContentService
    )

    image_vision_service = providers.Singleton(
        ImageVisionService, 
        ai_service=ai_content_service
    )

    user_service = providers.Singleton(
        UserService, 
        redis_client=redis_client
    )

    coin_list_service = providers.Singleton(
        CoinListService, 
        redis_client=redis_client, 
        http_client=http_client, 
        config=config.provided.coin_list_service
    )

    coin_alias_service = providers.Singleton(
        CoinAliasService, 
        redis_client=redis_client
    )

    parser_service = providers.Singleton(
        ParserService, 
        http_client=http_client
    )

    market_data_service = providers.Singleton(
        MarketDataService, 
        redis_client=redis_client, 
        http_client=http_client, 
        coin_list_service=coin_list_service, 
        config=config.provided.market_data
    )

    price_service = providers.Singleton(
        PriceService, 
        redis_client=redis_client, 
        market_data_service=market_data_service, 
        config=config.provided.price_service
    )

    news_service = providers.Singleton(
        NewsService, 
        redis_client=redis_client, 
        http_client=http_client
    )

    quiz_service = providers.Singleton(
        QuizService, 
        ai_content_service=ai_content_service
    )

    achievement_service = providers.Singleton(
        AchievementService, 
        market_data_service=market_data_service, 
        redis_client=redis_client
    )

    asic_service = providers.Singleton(
        AsicService, 
        parser_service=parser_service, 
        redis_client=redis_client
    )

    crypto_center_service = providers.Singleton(
        CryptoCenterService, 
        ai_service=ai_content_service, 
        news_service=news_service, 
        redis_client=redis_client
    )

    mining_service = providers.Singleton(
        MiningService, 
        market_data_service=market_data_service
    )

    mining_game_service = providers.Singleton(
        MiningGameService, 
        user_service=user_service, 
        asic_service=asic_service, 
        achievement_service=achievement_service, 
        redis_client=redis_client
    )

    verification_service = providers.Singleton(
        VerificationService, 
        user_service=user_service
    )

    admin_service = providers.Singleton(
        AdminService, 
        redis_client=redis_client, 
        bot=bot
    )

    moderation_service = providers.Singleton(
        ModerationService, 
        redis_client=redis_client, 
        bot=bot
    )

    security_service = providers.Singleton(
        SecurityService, 
        ai_content_service=ai_content_service, 
        image_vision_service=image_vision_service, 
        moderation_service=moderation_service, 
        redis_client=redis_client, 
        bot=bot
    )