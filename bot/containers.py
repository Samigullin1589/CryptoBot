# =================================================================================
# Файл: bot/containers.py
# Версия: "Distinguished Engineer" — ФИНАЛЬНАЯ ВЕРСИЯ (22.08.2025)
# Описание:
#   • Центральный DI-контейнер, адаптированный под новую, вложенную конфигурацию.
#   • Инициализирует Redis-клиент напрямую из DSN (REDIS_URL).
#   • Прокидывает в каждый сервис только его собственный, изолированный
#     блок настроек (например, settings.price_service), а не весь объект целиком.
# =================================================================================

from dependency_injector import containers, providers
from redis.asyncio import Redis

from bot.config.settings import Settings, settings
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


class Container(containers.DeclarativeContainer):
    """
    Основной контейнер приложения для внедрения зависимостей.
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
        ]
    )

    config = providers.Object(settings)

    redis_client = providers.Singleton(
        Redis.from_url,
        url=config.provided.REDIS_URL.get_secret_value(),
        decode_responses=True,
    )

    http_client = providers.Singleton(HttpClient)

    ai_content_service = providers.Singleton(AIContentService)
    
    image_vision_service = providers.Singleton(
        ImageVisionService,
        ai_service=ai_content_service,
    )

    user_service = providers.Singleton(
        UserService,
        redis_client=redis_client,
    )

    coin_list_service = providers.Singleton(
        CoinListService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.coin_list_service,
    )

    coin_alias_service = providers.Singleton(
        CoinAliasService,
        redis_client=redis_client,
    )
    
    parser_service = providers.Singleton(ParserService)

    market_data_service = providers.Singleton(
        MarketDataService,
        redis_client=redis_client,
        http_client=http_client,
        coin_list_service=coin_list_service,
        config=config.provided.market_data,
    )

    price_service = providers.Singleton(
        PriceService,
        redis_client=redis_client,
        market_data_service=market_data_service,
        config=config.provided.price_service,
    )

    news_service = providers.Singleton(
        NewsService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.news_service,
    )

    quiz_service = providers.Singleton(
        QuizService,
        ai_content_service=ai_content_service,
    )

    achievement_service = providers.Singleton(
        AchievementService,
        redis_client=redis_client,
        market_data_service=market_data_service,
    )

    asic_service = providers.Singleton(
        AsicService,
        redis_client=redis_client,
        parser_service=parser_service,
    )

    crypto_center_service = providers.Singleton(
        CryptoCenterService,
        redis_client=redis_client,
        news_service=news_service,
        ai_content_service=ai_content_service,
    )

    mining_service = providers.Singleton(
        MiningService,
        market_data_service=market_data_service,
    )
    
    mining_game_service = providers.Singleton(
        MiningGameService,
        redis_client=redis_client,
        user_service=user_service,
        asic_service=asic_service,
        achievement_service=achievement_service,
    )

    verification_service = providers.Singleton(
        VerificationService,
        user_service=user_service,
    )

    admin_service = providers.Singleton(
        AdminService,
        redis_client=redis_client,
    )

    moderation_service = providers.Singleton(
        ModerationService,
        redis_client=redis_client
    )

    security_service = providers.Singleton(
        SecurityService,
        ai_content_service=ai_content_service,
        image_vision_service=image_vision_service,
        moderation_service=moderation_service,
    )