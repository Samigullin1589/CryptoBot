# =================================================================================
# Файл: bot/containers.py
# Версия: "Distinguished Engineer" — ФИНАЛЬНАЯ ВЕРСИЯ (23.08.2025)
# Описание:
#   • Центральный DI-контейнер, управляющий жизненным циклом всех сервисов.
# ИСПРАВЛЕНИЕ: Исправлен вызов config.provided.REDIS_URL для совместимости с Pydantic V2.
# =================================================================================

from dependency_injector import containers, providers
from redis.asyncio import Redis
from aiogram import Bot

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


class Container(containers.DeclarativeContainer):
    """
    Основной контейнер приложения для внедрения зависимостей.
    """
    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot.main", "bot.utils.dependencies", "bot.jobs.scheduled_tasks",
        ],
        packages=["bot.handlers", "bot.middlewares",],
    )

    config = providers.Singleton(Settings)
    bot = providers.Singleton(Bot, token=config.provided.BOT_TOKEN.get_secret_value())

    # ИСПРАВЛЕНО: RedisDsn преобразуется в строку через str()
    redis_client = providers.Resource(
        Redis.from_url,
        url=str(config.provided.REDIS_URL),
        decode_responses=True,
    )
    http_client = providers.Resource(HttpClient, config=config.provided.endpoints)

    ai_content_service = providers.Singleton(AIContentService)
    image_vision_service = providers.Singleton(ImageVisionService, ai_service=ai_content_service)
    user_service = providers.Singleton(UserService, redis_client=redis_client)
    coin_list_service = providers.Singleton(CoinListService, redis_client=redis_client, http_client=http_client, config=config.provided.coin_list_service)
    coin_alias_service = providers.Singleton(CoinAliasService, redis_client=redis_client)
    parser_service = providers.Singleton(ParserService, http_client=http_client)
    market_data_service = providers.Singleton(MarketDataService, redis_client=redis_client, http_client=http_client, coin_list_service=coin_list_service, config=config.provided.market_data)
    price_service = providers.Singleton(PriceService, redis_client=redis_client, market_data_service=market_data_service, config=config.provided.price_service)
    news_service = providers.Singleton(NewsService, redis_client=redis_client, http_client=http_client)
    quiz_service = providers.Singleton(QuizService, ai_content_service=ai_content_service)
    achievement_service = providers.Singleton(AchievementService, market_data_service=market_data_service, redis_client=redis_client)
    asic_service = providers.Singleton(AsicService, parser_service=parser_service, redis_client=redis_client)
    crypto_center_service = providers.Singleton(CryptoCenterService, ai_service=ai_content_service, news_service=news_service, redis_client=redis_client)
    mining_service = providers.Singleton(MiningService, market_data_service=market_data_service)
    mining_game_service = providers.Singleton(MiningGameService, user_service=user_service, asic_service=asic_service, achievement_service=achievement_service, redis_client=redis_client)
    verification_service = providers.Singleton(VerificationService, user_service=user_service)
    admin_service = providers.Singleton(AdminService, redis_client=redis_client, bot=bot)
    moderation_service = providers.Singleton(ModerationService, redis_client=redis_client, bot=bot)
    security_service = providers.Singleton(SecurityService, ai_content_service=ai_content_service, image_vision_service=image_vision_service, moderation_service=moderation_service, redis_client=redis_client, bot=bot)