# =================================================================================
# Файл: bot/utils/dependencies.py (ВЕРСИЯ "Distinguished Engineer" - УСИЛЕННАЯ)
# Описание: DI-контейнер с логированием инициализации и асинхронной настройкой сервисов.
# =================================================================================

import logging
import aiohttp
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from bot.config.config import settings
from bot.utils.keys import KeyFactory

# Импортируем все сервисы
from bot.services.user_service import UserService
from bot.services.admin_service import AdminService
from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.services.parser_service import ParserService
from bot.services.security_service import SecurityService
from bot.services.coin_list_service import CoinListService
from bot.services.price_service import PriceService
from bot.services.asic_service import AsicService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.quiz_service import QuizService
from bot.services.market_data_service import MarketDataService
from bot.services.event_service import MiningEventService
from bot.services.achievement_service import AchievementService
from bot.services.market_service import AsicMarketService
from bot.services.mining_game_service import MiningGameService
from bot.services.verification_service import VerificationService

logger = logging.getLogger(__name__)

class Deps(BaseModel):
    """
    Data Injection контейнер для всех сервисов и клиентов.
    Гарантирует, что все компоненты приложения доступны в одном месте.
    """
    settings: Settings
    http_session: aiohttp.ClientSession
    redis_pool: Redis
    scheduler: AsyncIOScheduler
    bot: Bot
    keys: KeyFactory = Field(default_factory=KeyFactory)

    # Сервисы
    user_service: UserService
    admin_service: AdminService
    ai_content_service: AIContentService
    news_service: NewsService
    parser_service: ParserService
    quiz_service: QuizService
    event_service: MiningEventService
    achievement_service: AchievementService
    market_data_service: MarketDataService
    security_service: SecurityService
    coin_list_service: CoinListService
    asic_service: AsicService
    price_service: PriceService
    crypto_center_service: CryptoCenterService
    market_service: AsicMarketService
    mining_game_service: MiningGameService
    verification_service: VerificationService

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    async def build(cls, settings: Settings, http_session: aiohttp.ClientSession, redis_pool: Redis, bot: Bot) -> "Deps":
        """
        Асинхронный фабричный метод для безопасной сборки и настройки контейнера зависимостей.
        """
        logger.info("Начало сборки контейнера зависимостей (Deps)...")
        try:
            # Инициализация базовых сервисов
            user_service = UserService(redis=redis_pool)
            logger.info("UserService инициализирован.")
            
            admin_service = AdminService(redis=redis_pool, settings=settings, bot=bot)
            logger.info("AdminService инициализирован.")

            ai_content_service = AIContentService(api_key=settings.GEMINI_API_KEY.get_secret_value(), config=settings.ai)
            logger.info("AIContentService инициализирован.")

            news_service = NewsService(redis=redis_pool, http_session=http_session, config=settings.news_service)
            logger.info("NewsService инициализирован.")

            parser_service = ParserService(http_session=http_session, config=settings.endpoints)
            logger.info("ParserService инициализирован.")

            quiz_service = QuizService(ai_content_service=ai_content_service)
            logger.info("QuizService инициализирован.")

            event_service = MiningEventService(config=settings.events)
            logger.info("MiningEventService инициализирован.")
            
            coin_list_service = CoinListService(redis=redis_pool, http_session=http_session, settings=settings)
            logger.info("CoinListService инициализирован.")

            # Инициализация сервисов, зависящих от других
            market_data_service = MarketDataService(redis=redis_pool, http_session=http_session, settings=settings, coin_list_service=coin_list_service)
            logger.info("MarketDataService инициализирован.")

            achievement_service = AchievementService(redis=redis_pool, config=settings.achievements, market_data_service=market_data_service)
            logger.info("AchievementService инициализирован.")

            security_service = SecurityService(ai_service=ai_content_service, config=settings.threat_filter)
            logger.info("SecurityService инициализирован.")

            asic_service = AsicService(redis=redis_pool, parser_service=parser_service, config=settings.asic_service)
            logger.info("AsicService инициализирован.")

            price_service = PriceService(redis=redis_pool, config=settings.price_service, market_data_service=market_data_service)
            logger.info("PriceService инициализирован.")

            crypto_center_service = CryptoCenterService(redis=redis_pool, ai_service=ai_content_service, news_service=news_service, config=settings.crypto_center)
            logger.info("CryptoCenterService инициализирован.")

            market_service = AsicMarketService(redis=redis_pool, settings=settings, achievement_service=achievement_service, bot=bot)
            logger.info("AsicMarketService инициализирован.")
            
            scheduler_instance = AsyncIOScheduler(timezone="UTC")
            logger.info("AsyncIOScheduler инициализирован.")

            mining_game_service = MiningGameService(
                redis=redis_pool, scheduler=scheduler_instance, settings=settings, user_service=user_service,
                market_service=market_service, event_service=event_service,
                achievement_service=achievement_service, bot=bot
            )
            logger.info("MiningGameService инициализирован.")

            verification_service = VerificationService(user_service=user_service)
            logger.info("VerificationService инициализирован.")

            # Асинхронная настройка сервисов, которым это необходимо
            logger.info("Запуск асинхронной настройки сервисов...")
            await market_service.setup()
            await mining_game_service.setup()
            logger.info("Асинхронная настройка сервисов завершена.")

            deps_instance = cls(
                settings=settings, http_session=http_session, redis_pool=redis_pool,
                scheduler=scheduler_instance, bot=bot, user_service=user_service,
                admin_service=admin_service, ai_content_service=ai_content_service,
                news_service=news_service, parser_service=parser_service,
                quiz_service=quiz_service, event_service=event_service,
                achievement_service=achievement_service, market_data_service=market_data_service,
                security_service=security_service, coin_list_service=coin_list_service,
                asic_service=asic_service, price_service=price_service,
                crypto_center_service=crypto_center_service, market_service=market_service,
                mining_game_service=mining_game_service, verification_service=verification_service
            )
            logger.info("Контейнер зависимостей (Deps) успешно собран.")
            return deps_instance

        except Exception as e:
            logger.critical(f"Критическая ошибка при сборке контейнера зависимостей: {e}", exc_info=True)
            raise